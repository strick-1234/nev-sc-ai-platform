# -*- coding: utf-8 -*-
"""把融合数仓导出为一个 Excel 数据交付包（多工作表，可直接打开查看/用于报告）。

用法: .venv\Scripts\python.exe 融合平台\export_excel.py
输出: 融合平台\数据交付_新能源汽车售后供应链数据包.xlsx
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DB = HERE / "data" / "warehouse.db"
OUT = HERE / "数据交付_新能源汽车售后供应链数据包.xlsx"

DICT = [
    ("dim_products", "商品维度", "sku, name, category, unit_price"),
    ("dim_customers", "客户维度(经销商/服务站)", "cust_id, cust_name, region, grade"),
    ("dim_warehouses", "仓库维度(区域备件中心仓)", "wh_code, wh_name, region, capacity"),
    ("dim_vehicles", "车辆维度", "vehicle_id, plate, driver, carrier, capacity, status"),
    ("dim_suppliers", "供应商维度(扩展)", "supplier_id, name, city, lat, lon, on_time_rate"),
    ("fact_orders", "销售订单事实(52周)", "order_id, order_no, cust_id, sku, qty, amount, order_date, status"),
    ("fact_inventory", "库存事实(分仓,含账实差异)", "wh_code, sku, book_qty, actual_qty, safety_stock, diff_qty, last_check"),
    ("fact_shipments", "运单事实(含延迟/异常)", "shipment_id, order_no, vehicle_id, carrier, origin, dest, distance, status, delay_min, exception_type..."),
    ("fact_tracking", "轨迹事实(GPS)", "shipment_id, seq, ts, lng, lat, event"),
    ("fact_production", "生产工单事实", "work_order, sku, line, planned_qty, actual_qty, pass_rate, produce_date"),
    ("fact_complaints", "投诉事实", "complaint_id, cust_id, order_no, shipment_id, type, satisfaction, date, handled"),
    ("fact_alerts", "异常告警(ETL派生,分级闭环)", "alert_id, source, ref_id, type, level, description, status, create_time"),
    ("fact_sku_plan", "SKU计划策略(扩展)", "sku, abc_class, xyz_class, annual_value, supplier_id, lead_time_weeks, moq"),
    ("fact_inbound", "在途采购(扩展)", "po_id, sku, supplier_id, qty, eta_week, status"),
    ("fact_demand_weekly", "周需求序列(扩展,52周)", "sku, week, week_start, demand"),
    ("fact_stock_lot", "库存批次明细(库位/效期)", "wh_code, sku, location, batch_no, lot_qty, expiry_date, status"),
    ("fact_inout", "出入库流水", "wh_code, sku, io_type, qty, ref_no, ts"),
    ("fact_freight", "运单运费结算", "shipment_id, base_fee, fuel_fee, total, settle_status"),
]


def fetch(sql: str) -> pd.DataFrame:
    con = sqlite3.connect(DB)
    try:
        return pd.read_sql_query(sql, con)
    finally:
        con.close()


def sheet_write(writer: pd.ExcelWriter, name: str, df: pd.DataFrame) -> None:
    df.to_excel(writer, sheet_name=name, index=False)
    ws = writer.sheets[name]
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, col in enumerate(df.columns, start=1):
        w = min(max(len(str(col)), df[col].astype(str).str.len().max() if len(df) else 0) + 2, 46)
        ws.column_dimensions[chr(64 + i) if i <= 26 else "A"].width = w  # 简单宽度，超过 Z 不细调


def main():
    con = sqlite3.connect(DB)
    kpi = {}
    kpi["商品SKU数"] = con.execute("SELECT COUNT(*) FROM dim_products").fetchone()[0]
    kpi["客户数"] = con.execute("SELECT COUNT(*) FROM dim_customers").fetchone()[0]
    kpi["52周销售订单数"] = con.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
    kpi["52周销售金额(元)"] = round(con.execute("SELECT SUM(amount) FROM fact_orders").fetchone()[0], 2)
    kpi["分仓库存记录"] = con.execute("SELECT COUNT(*) FROM fact_inventory").fetchone()[0]
    kpi["运单数"] = con.execute("SELECT COUNT(*) FROM fact_shipments").fetchone()[0]
    kpi["GPS轨迹点数"] = con.execute("SELECT COUNT(*) FROM fact_tracking").fetchone()[0]
    kpi["生产工单数"] = con.execute("SELECT COUNT(*) FROM fact_production").fetchone()[0]
    kpi["投诉数"] = con.execute("SELECT COUNT(*) FROM fact_complaints").fetchone()[0]
    kpi["告警数(ETL派生)"] = con.execute("SELECT COUNT(*) FROM fact_alerts").fetchone()[0]
    kpi["未闭环告警"] = con.execute("SELECT COUNT(*) FROM fact_alerts WHERE status!='已闭环'").fetchone()[0]
    kpi["在途采购批次"] = con.execute("SELECT COUNT(*) FROM fact_inbound").fetchone()[0]
    kpi["库存账实准确率"] = f"{1 - con.execute('SELECT SUM(ABS(diff_qty)) FROM fact_inventory').fetchone()[0] / con.execute('SELECT SUM(book_qty) FROM fact_inventory').fetchone()[0]:.2%}"
    ontime_ok = con.execute("SELECT COUNT(*) FROM fact_shipments WHERE status='已签收' AND delay_min=0").fetchone()[0]
    ontime_all = con.execute("SELECT COUNT(*) FROM fact_shipments WHERE status='已签收'").fetchone()[0]
    kpi["准时签收率"] = f"{ontime_ok / ontime_all:.2%}" if ontime_all else "-"
    con.close()

    intro = pd.DataFrame({
        "项目": ["数据交付包：新能源汽车售后供应链（融合平台）",
                "生成日期", "随机种子", "数据来源",
                "数据性质", "数仓文件", "重建命令",
                "说明1", "说明2", "说明3"],
        "内容": ["物流数据集成(5系统→ETL→数仓) + AI计划员所用数据",
                date.today().isoformat(), "20260906（可复现）", "融合平台/data/warehouse.db",
                "模拟生成、口径真实，用于功能演示与教学原型",
                "融合平台/data/warehouse.db",
                "python 融合平台/build_data.py",
                "SKU0001 动力电芯为主角：上海仓仅180件<安全库存620，已触发缺货预警",
                "周需求=销售订单按SKU×周聚合；ABC按年销售额累计占比；告警由ETL自动派生",
                "各表字段说明见下方『数据字典』工作表"],
    })
    summary = pd.DataFrame(list(kpi.items()), columns=["指标", "数值"])

    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        intro.to_excel(writer, sheet_name="00_说明", index=False)
        ws = writer.sheets["00_说明"]
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 110
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)
        summary.to_excel(writer, sheet_name="00_关键指标", index=False)
        ws = writer.sheets["00_关键指标"]
        ws.column_dimensions["A"].width = 24
        ws.column_dimensions["B"].width = 20
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)
        pd.DataFrame(DICT, columns=["表名", "含义", "关键字段"]).to_excel(
            writer, sheet_name="00_数据字典", index=False)
        ws = writer.sheets["00_数据字典"]
        for c, w in zip("ABC", (18, 42, 90)):
            ws.column_dimensions[c].width = w
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)

        # 主数据各表
        sheet_write(writer, "01_商品SKU", fetch("SELECT * FROM dim_products ORDER BY sku"))
        sheet_write(writer, "02_客户", fetch("SELECT * FROM dim_customers ORDER BY cust_id"))
        sheet_write(writer, "03_供应商", fetch("SELECT * FROM dim_suppliers ORDER BY supplier_id"))
        sheet_write(writer, "04_SKU计划策略ABC_XYZ", fetch("""SELECT sp.sku, p.name, sp.abc_class, sp.xyz_class,
            sp.annual_value, sp.lead_time_weeks, sp.moq, s.name AS supplier_name, s.city, s.on_time_rate
            FROM fact_sku_plan sp JOIN dim_products p ON sp.sku=p.sku
            JOIN dim_suppliers s ON sp.supplier_id=s.supplier_id ORDER BY sp.annual_value DESC"""))
        sheet_write(writer, "05_库存分仓", fetch("""SELECT i.wh_code, w.wh_name, i.sku, p.name,
            i.book_qty, i.actual_qty, i.safety_stock, i.diff_qty, i.last_check
            FROM fact_inventory i JOIN dim_warehouses w ON i.wh_code=w.wh_code
            JOIN dim_products p ON i.sku=p.sku ORDER BY i.sku, i.wh_code"""))
        sheet_write(writer, "06_在途采购", fetch("SELECT * FROM fact_inbound ORDER BY sku"))
        sheet_write(writer, "07_周需求序列52周", fetch("""SELECT dw.sku, p.name, dw.week, dw.week_start, dw.demand
            FROM fact_demand_weekly dw JOIN dim_products p ON dw.sku=p.sku ORDER BY dw.sku, dw.week"""))
        sheet_write(writer, "08_销售订单(前2万样本)", fetch("""SELECT o.order_no, o.order_date, o.status, o.sku, p.name AS product_name,
            o.qty, o.amount, o.cust_id, c.cust_name, c.region, c.grade
            FROM fact_orders o JOIN dim_products p ON o.sku=p.sku
            JOIN dim_customers c ON o.cust_id=c.cust_id ORDER BY o.order_no LIMIT 20000"""))
        sheet_write(writer, "09_运单", fetch("SELECT * FROM fact_shipments ORDER BY shipment_id"))
        sheet_write(writer, "10_GPS轨迹", fetch("SELECT * FROM fact_tracking ORDER BY shipment_id, seq"))
        sheet_write(writer, "11_生产工单", fetch("SELECT * FROM fact_production ORDER BY work_order"))
        sheet_write(writer, "12_客户投诉", fetch("SELECT * FROM fact_complaints ORDER BY complaint_id"))
        sheet_write(writer, "13_异常告警", fetch("SELECT * FROM fact_alerts ORDER BY alert_id"))
        sheet_write(writer, "14_库存批次明细", fetch("SELECT * FROM fact_stock_lot ORDER BY wh_code, sku, batch_no"))
        sheet_write(writer, "15_出入库流水", fetch("SELECT * FROM fact_inout ORDER BY ts DESC"))
        sheet_write(writer, "16_运单运费", fetch("SELECT * FROM fact_freight ORDER BY total DESC"))
    print("已生成:", OUT)
    print("大小 KB:", round(OUT.stat().st_size / 1024, 1))


if __name__ == "__main__":
    main()
