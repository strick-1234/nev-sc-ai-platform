# -*- coding: utf-8 -*-
"""融合平台 · 数仓访问助手（warehouse.db）。

数据口径：
- 可用库存 = 全网实际库存(fact_inventory.actual_qty 汇总) + 在途采购(fact_inbound)
- SKU 策略（ABC/XYZ/提前期/MOQ/供应商）来自 fact_sku_plan + dim_suppliers
- 需求序列来自 fact_demand_weekly（52 周，ETL 由销售订单聚合）
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "warehouse.db"


def get_conn() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(f"数仓不存在: {DB}\n请先运行: python 融合平台/build_data.py")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def resolve_product(key: str) -> dict | None:
    """按 SKU 或名称模糊查找产品，返回基础信息或候选列表。"""
    con = get_conn()
    key = key.strip().upper()
    row = con.execute(
        """SELECT p.sku, p.name, p.category, p.unit_price, sp.abc_class, sp.xyz_class,
                  sp.lead_time_weeks, sp.moq, s.supplier_id, s.name AS supplier_name,
                  s.city, s.on_time_rate, sp.annual_value
           FROM dim_products p
           JOIN fact_sku_plan sp ON p.sku = sp.sku
           JOIN dim_suppliers s ON sp.supplier_id = s.supplier_id
           WHERE p.sku = ?""",
        (key,),
    ).fetchone()
    if row is not None:
        return dict(row)
    rows = con.execute(
        """SELECT sku, name FROM dim_products WHERE sku LIKE ? OR name LIKE ? LIMIT 10""",
        (f"%{key}%", f"%{key.strip()}%"),
    ).fetchall()
    if len(rows) == 1:
        return resolve_product(rows[0]["sku"])
    if rows:
        return {"candidates": [dict(r) for r in rows]}
    return None


def inventory_rows(sku: str) -> list[sqlite3.Row]:
    con = get_conn()
    return con.execute(
        "SELECT wh_code, actual_qty, book_qty, safety_stock FROM fact_inventory WHERE sku = ? ORDER BY wh_code",
        (sku,),
    ).fetchall()


def inbound_rows(sku: str) -> list[sqlite3.Row]:
    con = get_conn()
    return con.execute(
        "SELECT po_id, qty, eta_week FROM fact_inbound WHERE sku = ? AND status = '在途'", (sku,)
    ).fetchall()


def demand_series(sku: str) -> list[tuple[int, str, float]]:
    con = get_conn()
    return [
        (r["week"], r["week_start"], r["demand"])
        for r in con.execute(
            "SELECT week, week_start, demand FROM fact_demand_weekly WHERE sku = ? ORDER BY week", (sku,)
        )
    ]


def latest_week_no() -> int:
    con = get_conn()
    return con.execute("SELECT MAX(week) FROM fact_demand_weekly").fetchone()[0]
