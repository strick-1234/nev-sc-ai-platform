# -*- coding: utf-8 -*-
"""融合平台工具②：需求预测（52 周周需求 → 季节分解 + 水平 + 波动σ）。"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

from . import db


def _season_index(series) -> dict[int, float]:
    grand = statistics.fmean(d for _, _, d in series) or 1.0
    by_month: dict[int, list[float]] = {}
    for _, wstart, d in series:
        by_month.setdefault(int(wstart[5:7]), []).append(d)
    return {m: statistics.fmean(v) / grand for m, v in by_month.items()}


def _level_sigma(series, idx) -> tuple[float, float]:
    tail = series[-12:]
    deseason = [d / max(idx.get(int(wstart[5:7]), 1.0), 0.3) for _, wstart, d in tail]
    level = statistics.fmean(deseason)
    sigma = statistics.pstdev(deseason) if len(deseason) > 1 else level * 0.2
    return level, sigma


def forecast_demand(sku: str, weeks: int = 4) -> dict:
    info = db.resolve_product(sku)
    if info is None or "candidates" in info:
        return {"ok": False, "text": f"未找到产品「{sku}」。"}
    weeks = max(1, min(int(weeks), 8))
    series = db.demand_series(info["sku"])
    idx = _season_index(series)
    level, sigma = _level_sigma(series, idx)
    last_date = date.fromisoformat(series[-1][1])

    forecast = []
    for k in range(1, weeks + 1):
        d = last_date + timedelta(weeks=k)
        forecast.append({
            "week": db.latest_week_no() + k, "week_start": d.isoformat(),
            "demand": max(0, round(level * idx.get(d.month, 1.0))),
        })
    total = sum(f["demand"] for f in forecast)
    result = {
        "ok": True, "sku": info["sku"], "name": info["name"], "xyz_class": info["xyz_class"],
        "level_per_week": round(level, 1), "weekly_volatility_sigma": round(sigma, 1),
        "forecast": forecast, "forecast_total": total,
    }
    if info["xyz_class"] == "Z":
        result["text"] = (
            f"【{info['sku']} {info['name']}】Z 类间歇型需求，波动大（σ≈{sigma:.0f}）。"
            f"未来 {weeks} 周预测合计约 {total:,}，置信度低——建议按订单/看板拉动管理，预测仅参考。"
        )
    else:
        result["text"] = (
            f"【{info['sku']} {info['name']}】基于 52 周销售历史（含季节与趋势）预测未来 {weeks} 周："
            + "、".join(f"W{f['week']}≈{f['demand']:,}" for f in forecast)
            + f"，合计约 {total:,}；周波动 σ≈{sigma:.0f}（用于安全库存测算）。"
        )
    return result
