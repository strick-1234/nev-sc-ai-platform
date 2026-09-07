# -*- coding: utf-8 -*-
"""融合平台工具④：缺料风险模拟（供应商延期 what-if）。"""
from __future__ import annotations

from . import db
from .forecast_tool import forecast_demand
from .replenish_tool import calc_replenishment


def simulate_stockout(sku: str, delay_weeks: int = 0, assume_order: bool = True) -> dict:
    info = db.resolve_product(sku)
    if info is None or "candidates" in info:
        return {"ok": False, "text": f"未找到产品「{sku}」。"}
    p = dict(info)
    delay = max(0, int(delay_weeks))
    L = p["lead_time_weeks"]
    arrival_week = L + delay

    whs = db.inventory_rows(p["sku"])
    inbs = db.inbound_rows(p["sku"])
    available = sum(r["actual_qty"] for r in whs) + sum(r["qty"] for r in inbs)
    fc = forecast_demand(p["sku"], weeks=max(arrival_week + 1, 6))
    dem = [f["demand"] for f in fc["forecast"]]
    order_qty = calc_replenishment(p["sku"])["suggested_order_qty"] if assume_order else 0

    stock, stockout_week, peak, shortage_weeks = available, None, 0, 0
    for i, d in enumerate(dem, start=1):
        if assume_order and i == arrival_week:
            stock += order_qty
        stock -= d
        if stock < 0:
            shortage_weeks += 1
            peak = max(peak, -stock)
            if stockout_week is None:
                stockout_week = i
    if stockout_week is None:
        risk = "安全"
    elif assume_order and stockout_week < arrival_week:
        risk = "高风险（到货前即断料）"
    elif not assume_order and stockout_week <= L:
        risk = "高风险"
    else:
        risk = "中风险"

    wno = db.latest_week_no()
    result = {
        "ok": True, "sku": p["sku"], "name": p["name"], "abc_class": p["abc_class"],
        "delay_weeks": delay, "lead_time_weeks": L, "available": available,
        "assume_order": assume_order, "order_qty_if_assumed": order_qty,
        "stockout_week_in_sim": stockout_week, "peak_shortage_units": peak,
        "shortage_weeks": shortage_weeks, "risk_level": risk,
    }
    lines = [
        f"【{p['sku']} {p['name']}】缺料风险模拟：当前可用 {available:,}，提前期 {L} 周，"
        f"假设供应商延期 {delay} 周（到货 W{wno + arrival_week}）"
        + ("，按建议下单补齐。" if order_qty else "，且本周不下单。"),
    ]
    if stockout_week is None:
        lines.append(f"✅ 预测窗口内库存始终为正，延期 {delay} 周也不断料。")
    else:
        lines.append(f"⚠️ 预计 W{wno + stockout_week} 库存耗尽，最大缺口约 {peak:,} 件，累计影响 {shortage_weeks} 周。")
        if p["abc_class"] == "A":
            lines.append("该 SKU 为 A 类关键件，建议启动加急/跨仓调拨或调整补货计划。")
        lines.append("建议：① 联系供应商确认加急/分批交付；② 评估替代料或跨仓调拨；③ 提高服务水平重算补货方案。")
    result["text"] = "\n".join(lines)
    return result
