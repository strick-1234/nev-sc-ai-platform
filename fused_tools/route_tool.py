# -*- coding: utf-8 -*-
"""融合平台工具⑤：取货路径优化（华东备件中心仓 → 供应商，最近邻+2-opt）。"""
from __future__ import annotations

import math

from . import db

ROAD_FACTOR = 1.3
DEPOT = {"WH-SH": ("华东备件中心仓(上海)", 31.23, 121.47)}  # (lat, lon)


def _dist(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    return 2 * r * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)) * ROAD_FACTOR


def _total(seq, dmat):
    return sum(dmat[seq[i]][seq[i + 1]] for i in range(len(seq) - 1))


def _two_opt(seq, dmat):
    best = seq[:]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best) - 1):
                cand = best[:i] + best[i : j + 1][::-1] + best[j + 1:]
                if _total(cand, dmat) < _total(best, dmat) - 1e-9:
                    best = cand
                    improved = True
    return best


def optimize_route(supplier_ids: str) -> dict:
    con = db.get_conn()
    tokens = [t.split("(")[0].strip() for t in supplier_ids.replace("，", ",").split(",") if t.strip()]
    sups = []
    for t in tokens:
        row = con.execute(
            "SELECT * FROM dim_suppliers WHERE supplier_id=? OR city=? OR name LIKE ?",
            (t.upper(), t, f"%{t}%"),
        ).fetchone()
        if row is None:
            return {"ok": False, "text": f"供应商「{t}」未找到。可用编号：S-01~S-10。"}
        if row not in sups:
            sups.append(row)
    if len(sups) < 2:
        return {"ok": False, "text": "请至少提供 2 家供应商做路线优化。"}

    dep = DEPOT["WH-SH"]
    pts = [(dep[1], dep[2])] + [(r["lat"], r["lon"]) for r in sups]
    dmat = [[_dist(pts[i][0], pts[i][1], pts[j][0], pts[j][1]) for j in range(len(pts))] for i in range(len(pts))]
    inner = list(range(1, len(pts)))

    def solve(start_order):
        return _two_opt([0] + start_order + [0], dmat), _total(_two_opt([0] + start_order + [0], dmat), dmat)

    nn, rest = [], inner[:]
    while rest:
        prev = 0 if not nn else nn[-1]
        nxt = min(rest, key=lambda k, pp=prev: dmat[pp][k])
        nn.append(nxt)
        rest.remove(nxt)
    best_seq, best_dist = None, math.inf
    for rot in range(len(nn)):
        cand = nn[rot:] + nn[:rot]
        seq, d = solve(cand)
        if d < best_dist:
            best_seq, best_dist = seq, d
    seq, d = solve(nn[::-1])
    if d < best_dist:
        best_seq, best_dist = seq, d

    legs = []
    for a, b in zip(best_seq[:-1], best_seq[1:]):
        na = dep[0] if a == 0 else f"{sups[a-1]['supplier_id']} {sups[a-1]['name']}({sups[a-1]['city']})"
        nb = dep[0] if b == 0 else f"{sups[b-1]['supplier_id']} {sups[b-1]['name']}({sups[b-1]['city']})"
        legs.append({"from": na, "to": nb, "km": round(dmat[a][b], 1)})
    parts = {}
    for r in sups:
        ps = con.execute(
            "SELECT p.name FROM dim_products p JOIN fact_sku_plan sp ON p.sku=sp.sku WHERE sp.supplier_id=?",
            (r["supplier_id"],),
        ).fetchall()
        parts[r["supplier_id"]] = "、".join(x["name"] for x in ps)
    result = {
        "ok": True, "origin": dep[0], "legs": legs,
        "total_km": round(best_dist, 1), "parts_by_supplier": parts,
    }
    text = [f"【取货路径优化】从{dep[0]}出发：" + " → ".join(legs[i]["to"].split("(")[0] for i in range(len(legs)))
            + f"，总里程约 {result['total_km']} km。", "分段里程："]
    for lg in legs:
        text.append(f"  {lg['from']} → {lg['to']}：{lg['km']} km")
    result["text"] = "\n".join(text)
    return result
