# -*- coding: utf-8 -*-
"""融合平台工具③：补货计算（全网口径）。

口径：服务水平按 ABC 分层（A 97.5% / B 95% / C 90%），
安全库存 SS = z·σ·√L，ROP = 提前期需求 + SS，
可用 = 全网实际库存 + 在途采购；可用 < ROP → 补至目标库存（MOQ 取整）。
"""
from __future__ import annotations

import math

from . import db
from .forecast_tool import forecast_demand

_SL_Z = {"A": (0.975, 1.96), "B": (0.95, 1.645), "C": (0.90, 1.282)}
_Z_TABLE = [(0.999, 3.09), (0.99, 2.33), (0.975, 1.96), (0.95, 1.645),
            (0.90, 1.282), (0.85, 1.036), (0.80, 0.842)]
REVIEW_CYCLE = 4


def _z(sl: float) -> float:
    return min(_Z_TABLE, key=lambda t: abs(t[0] - sl))[1]


def calc_replenishment(sku: str, service_level: float | None = None) -> dict:
    info = db.resolve_product(sku)
    if info is None or "candidates" in info:
        return {"ok": False, "text": f"未找到产品「{sku}」。"}
    p = dict(info)
    sl = float(service_level) if service_level is not None else _SL_Z[p["abc_class"]][0]
    z = _z(sl)
    L = p["lead_time_weeks"]
    fc = forecast_demand(p["sku"], weeks=L + REVIEW_CYCLE)
    if not fc["ok"]:
        return fc
    sigma = fc["weekly_volatility_sigma"]
    dem = [f["demand"] for f in fc["forecast"]]
    dem_lead, dem_lead_cycle = sum(dem[:L]), sum(dem[: L + REVIEW_CYCLE])
    ss = z * sigma * math.sqrt(L)
    rop = math.ceil(dem_lead + ss)
    target = math.ceil(dem_lead_cycle + ss)

    whs = db.inventory_rows(p["sku"])
    inbs = db.inbound_rows(p["sku"])
    available = sum(r["actual_qty"] for r in whs) + sum(r["qty"] for r in inbs)
    need_order = available < rop
    moq = p["moq"]
    qty = math.ceil(max(0.0, target - available) / moq) * moq if need_order else 0

    cum, stockout_week = 0, None
    for f in fc["forecast"]:
        cum += f["demand"]
        if cum > available:
            stockout_week = f["week"]
            break

    result = {
        "ok": True, "sku": p["sku"], "name": p["name"],
        "abc_class": p["abc_class"], "xyz_class": p["xyz_class"],
        "service_level": sl, "lead_time_weeks": L, "moq": moq,
        "forecast_lead_demand": dem_lead, "safety_stock": round(ss), "rop": rop,
        "target_stock": target, "available": available,
        "on_hand": sum(r["actual_qty"] for r in whs),
        "in_transit": sum(r["qty"] for r in inbs),
        "need_order": need_order, "suggested_order_qty": qty,
        "stockout_week_if_no_order": stockout_week,
    }
    lines = [
        f"【{p['sku']} {p['name']}】{p['abc_class']}{p['xyz_class']} 类，提前期 {L} 周，MOQ {moq:,}。",
        f"策略：{p['abc_class']} 类服务水平 {sl*100:.1f}%（z≈{z:.3f}）；安全库存 = z×σ×√L ≈ {round(ss):,}；"
        f"ROP = 提前期需求({dem_lead:,}) + 安全库存({round(ss):,}) = {rop:,}。",
        f"当前可用 = 全网实际 {result['on_hand']:,} + 在途 {result['in_transit']:,} = {available:,}。",
    ]
    if need_order:
        lines.append(f"可用 {available:,} < ROP {rop:,}，建议补货 {qty:,}（补至目标库存 {target:,}，按 MOQ 取整）。")
        if stockout_week:
            lines.append(f"⚠️ 若本周不下单，按预测需求预计 W{stockout_week} 前后断料。")
    else:
        lines.append(f"可用 {available:,} ≥ ROP {rop:,}，当前无需补货。")
    if p["xyz_class"] == "Z":
        lines.append("注意：Z 类间歇件波动大，建议人工复核或订单驱动。")
    result["text"] = "\n".join(lines)
    return result
