# -*- coding: utf-8 -*-
"""融合平台工具①：全网库存查询（分仓明细 + 在途采购）。"""
from __future__ import annotations

from . import db


def query_inventory(sku: str) -> dict:
    info = db.resolve_product(sku)
    if info is None:
        return {"ok": False, "text": f"未找到产品「{sku}」，请检查 SKU 或名称。"}
    if "candidates" in info:
        names = "、".join(f"{c['sku']} {c['name']}" for c in info["candidates"])
        return {"ok": False, "text": f"「{sku}」匹配到多个产品，请用完整 SKU：{names}"}

    whs = db.inventory_rows(info["sku"])
    inbs = db.inbound_rows(info["sku"])
    on_hand = sum(r["actual_qty"] for r in whs)
    in_transit = sum(r["qty"] for r in inbs)
    available = on_hand + in_transit
    series = db.demand_series(info["sku"])
    avg = round(sum(d for _, _, d in series[-4:]) / 4, 1) if series else 0
    cover = round(available / avg, 1) if avg > 0 else 0
    wh_detail = [
        {"wh_code": r["wh_code"], "actual": r["actual_qty"], "safety": r["safety_stock"]} for r in whs
    ]
    result = {
        "ok": True,
        "sku": info["sku"], "name": info["name"], "category": info["category"],
        "unit_price": info["unit_price"], "abc_class": info["abc_class"], "xyz_class": info["xyz_class"],
        "supplier": f"{info['supplier_name']}({info['city']})", "lead_time_weeks": info["lead_time_weeks"],
        "supplier_on_time_rate": info["on_time_rate"],
        "on_hand": on_hand, "in_transit": in_transit, "inbound_detail": [dict(r) for r in inbs],
        "available": available, "warehouse_detail": wh_detail,
        "recent_avg_demand_per_week": avg, "cover_weeks": cover,
    }
    status = "库存偏紧" if cover < 1.2 else ("库存健康" if cover < 3 else "库存偏高")
    lines = [
        f"【{info['sku']} {info['name']}】{info['abc_class']}{info['xyz_class']} 类，单价 {info['unit_price']:,.0f} 元；"
        f"供应商 {info['supplier_name']}({info['city']})，提前期 {info['lead_time_weeks']} 周，到货准时率 {info['on_time_rate']*100:.1f}%。",
        f"全网实际库存 {on_hand:,}（分仓：" + "、".join(f"{r['wh_code']} {r['actual']:,}" for r in wh_detail) + "），",
    ]
    if in_transit:
        lines.append(f"在途采购 {in_transit:,}" + "；".join(
            f"{r['qty']:,} 件约 {r['eta_week']} 周后到" for r in inbs) + "；")
    else:
        lines.append("无在途采购；")
    lines.append(f"可用合计 {available:,}，近 4 周平均周需求 {avg:,.1f}，可用约覆盖 {cover} 周 → 状态：{status}。")
    if any(r["actual"] < r["safety"] for r in wh_detail):
        lines.append("⚠️ 存在分仓实际库存低于安全库存（缺货预警），详见告警列表。")
    result["text"] = "\n".join(lines)
    return result
