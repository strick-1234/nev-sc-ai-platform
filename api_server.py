# -*- coding: utf-8 -*-
"""融合平台 · 聚合/服务层 API（Python 版，替代原 Node Express 后端）

- 复用原后端 9 个接口（字段/JSON 完全对齐），数据源 = 融合数仓 warehouse.db
- 新增 /api/ai/chat、/api/ai/reset（AI 计划员）
- 端口 8503

运行: .venv\Scripts\python.exe 融合平台\api_server.py
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
DB = HERE / "data" / "warehouse.db"
DATASOURCES = HERE / "data" / "raw" / "datasources.json"

LEVEL_RANK = {"高": 0, "中": 1, "低": 2}

# 告警处置建议 + 升级路径（与 SOP 联动）
ALERT_RULE = {
    "缺货预警": ("加急采购 / 跨仓调拨 / 替代料验证", "高 → L2 升级：供应链科长协调"),
    "延迟预警": ("催交 / 加急运输 / 调整到货顺序", "高 → L2：加急运输 + 跨库调拨"),
    "库存差异": ("发起盘点 / 差异调整审批", "低 → 计划员处理"),
    "破损": ("质检判责 / 退换处理", "中 → 质量 + 客服协同"),
    "丢件": ("承运商索赔 / 补发", "高 → L2/L3：跨部门应急"),
    "临期预警": ("促销出清 / 优先出库", "中 → 计划员处理"),
}

from fused_tools import db as fdb, replenish_tool  # noqa: E402
from fused_tools.forecast_tool import forecast_demand  # noqa: E402
from fused_tools.forecast_tool import _level_sigma, _season_index  # noqa: E402
from fused_tools.replenish_tool import REVIEW_CYCLE, _SL_Z, _z  # noqa: E402


def q(sql: str, params: tuple = ()):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params)]
    finally:
        con.close()


def q1(sql: str, params: tuple = ()):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        r = con.execute(sql, params).fetchone()
        return dict(r) if r else {}
    finally:
        con.close()


def overview():
    total_orders = q1("SELECT COUNT(*) c FROM fact_orders").get("c", 0)
    total_shipments = q1("SELECT COUNT(*) c FROM fact_shipments").get("c", 0)
    on_transit = q1("SELECT COUNT(*) c FROM fact_shipments WHERE status='在途'").get("c", 0)
    delivered = q1("SELECT COUNT(*) c FROM fact_shipments WHERE status='已签收'").get("c", 0)
    pending = q1("SELECT COUNT(*) c FROM fact_shipments WHERE status='待发运'").get("c", 0)
    exception = q1("SELECT COUNT(*) c FROM fact_shipments WHERE status='异常'").get("c", 0)
    delayed = q1("SELECT COUNT(*) c FROM fact_shipments WHERE delay_min > 0").get("c", 0)
    total_alerts = q1("SELECT COUNT(*) c FROM fact_alerts").get("c", 0)
    pending_alerts = q1("SELECT COUNT(*) c FROM fact_alerts WHERE status='待处理'").get("c", 0)
    processing = q1("SELECT COUNT(*) c FROM fact_alerts WHERE status='处理中'").get("c", 0)
    closed = q1("SELECT COUNT(*) c FROM fact_alerts WHERE status='已闭环'").get("c", 0)
    inv = q1("SELECT COALESCE(SUM(book_qty),0) b, COALESCE(SUM(ABS(diff_qty)),0) d FROM fact_inventory")
    low_stock = q1("SELECT COUNT(*) c FROM fact_inventory WHERE actual_qty < safety_stock").get("c", 0)
    total_complaints = q1("SELECT COUNT(*) c FROM fact_complaints").get("c", 0)
    avg_sat = q1("SELECT ROUND(AVG(satisfaction),2) a FROM fact_complaints").get("a")
    return {
        "totalOrders": total_orders,
        "totalShipments": total_shipments,
        "onTransit": on_transit,
        "delivered": delivered,
        "pendingShip": pending,
        "exceptionShip": exception,
        "delayed": delayed,
        "ontimeRate": round(1 - delayed / total_shipments, 4) if total_shipments else 1,
        "totalAlerts": total_alerts,
        "pendingAlerts": pending_alerts,
        "processingAlerts": processing,
        "closedAlerts": closed,
        "inventoryAccuracy": round(1 - inv["d"] / inv["b"], 4) if inv.get("b") else 1,
        "lowStock": low_stock,
        "totalComplaints": total_complaints,
        "avgSatisfaction": avg_sat,
    }


def shipments():
    return sorted(q("SELECT * FROM fact_shipments"), key=lambda r: -r["delay_min"])


def alerts():
    rows = q("SELECT * FROM fact_alerts")
    for r in rows:
        sug = ALERT_RULE.get(r["type"], ("人工研判", "按级别处理"))
        r["suggestion"] = sug[0]
        r["escalation"] = sug[1]
    return sorted(rows, key=lambda r: (LEVEL_RANK.get(r["level"], 9), r["alert_id"]))


def inventory():
    return q("""
        SELECT fi.*, dp.name AS product_name, dp.category, dw.wh_name
        FROM fact_inventory fi
        LEFT JOIN dim_products dp ON fi.sku = dp.sku
        LEFT JOIN dim_warehouses dw ON fi.wh_code = dw.wh_code
        ORDER BY ABS(fi.diff_qty) DESC
    """)


def inventory_summary():
    rows = q("""
        SELECT dw.wh_code, dw.wh_name, dw.region,
               SUM(fi.book_qty) AS book, SUM(fi.actual_qty) AS actual,
               SUM(ABS(fi.diff_qty)) AS diff_abs,
               SUM(CASE WHEN fi.actual_qty < fi.safety_stock THEN 1 ELSE 0 END) AS low_count
        FROM fact_inventory fi
        LEFT JOIN dim_warehouses dw ON fi.wh_code = dw.wh_code
        GROUP BY fi.wh_code ORDER BY diff_abs DESC
    """)
    for r in rows:
        r["accuracy"] = round(1 - r["diff_abs"] / r["book"], 4) if r["book"] else 1
    return rows


_CACHE = {"mtime": None, "data": None}


def _load_plan_weekly():
    """单连接批量加载：SKU 计划参数 + 周需求 + 全网库存/在途（按 DB mtime 缓存）。"""
    mt = DB.stat().st_mtime
    if _CACHE["mtime"] == mt and _CACHE["data"]:
        return _CACHE["data"]
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    plan = {r["sku"]: dict(r) for r in con.execute(
        "SELECT sp.*, p.name FROM fact_sku_plan sp JOIN dim_products p ON sp.sku = p.sku")}
    weekly = {}
    for r in con.execute("SELECT sku, week, week_start, demand FROM fact_demand_weekly ORDER BY sku, week"):
        weekly.setdefault(r["sku"], []).append((r["week"], r["week_start"], r["demand"]))
    inv = {r["sku"]: r["a"] for r in con.execute("SELECT sku, SUM(actual_qty) a FROM fact_inventory GROUP BY sku")}
    inb = {r["sku"]: r["q"] for r in con.execute(
        "SELECT sku, SUM(qty) q FROM fact_inbound WHERE status='在途' GROUP BY sku")}
    con.close()
    _CACHE["mtime"] = mt
    _CACHE["data"] = (plan, weekly, inv, inb)
    return _CACHE["data"]


def proposal():
    """全网补货建议单：批量计算（单连接 + 缓存），返回需补货清单（按建议量排序）。"""
    plan, weekly, inv, inb = _load_plan_weekly()
    need = []
    for sku, p in plan.items():
        series = weekly.get(sku, [])
        if len(series) < 3:
            continue
        idx = _season_index(series)
        level, sigma = _level_sigma(series, idx)
        L = p["lead_time_weeks"]
        last_date = date.fromisoformat(series[-1][1])
        dem = [max(0, round(level * idx.get((last_date + timedelta(weeks=k)).month, 1.0)))
               for k in range(1, L + REVIEW_CYCLE + 1)]
        ss = _z(_SL_Z[p["abc_class"]][0]) * sigma * math.sqrt(L)
        rop = math.ceil(sum(dem[:L]) + ss)
        target = math.ceil(sum(dem[: L + REVIEW_CYCLE]) + ss)
        available = (inv.get(sku, 0) or 0) + (inb.get(sku, 0) or 0)
        if available < rop:
            moq = p["moq"]
            qty = math.ceil(max(0.0, target - available) / moq) * moq
            cum, swo = 0, None
            for i, dd in enumerate(dem, start=1):
                cum += dd
                if cum > available:
                    swo = 52 + i
                    break
            need.append({
                "sku": sku, "name": p["name"], "abc_class": p["abc_class"],
                "xyz_class": p["xyz_class"], "available": available, "rop": rop,
                "suggested_order_qty": qty, "stockout_week": swo,
                "lead_time_weeks": L, "moq": moq, "service_level": _SL_Z[p["abc_class"]][0],
            })
    need.sort(key=lambda x: -x["suggested_order_qty"])
    return need


def forecast_accuracy():
    """全部 SKU 的预测可靠性评估（近 8 周朴素基线 MAPE，批量计算）。"""
    plan, weekly, _, _ = _load_plan_weekly()
    out = []
    for sku, p in plan.items():
        vals = [d for _, _, d in weekly.get(sku, [])[-8:]]
        mape = None
        if len(vals) >= 3:
            errs = [abs(vals[i] - vals[i - 1]) / vals[i - 1] for i in range(1, len(vals)) if vals[i - 1] > 0]
            mape = round(sum(errs) / len(errs), 4) if errs else None
        if mape is None:
            rel = "样本不足"
        elif mape < 0.30:
            rel = "可靠"
        elif mape < 0.60:
            rel = "一般"
        else:
            rel = "不可靠"
        out.append({"sku": sku, "name": p["name"], "abc_class": p["abc_class"],
                    "xyz_class": p["xyz_class"], "mape": mape, "reliability": rel})
    return out


def sku_detail(sku: str):
    info = fdb.resolve_product(sku)
    if info is None:
        return {"error": "未找到产品"}
    if "candidates" in info:
        return {"error": "匹配多个产品", "candidates": info["candidates"]}
    wh_name = {r["wh_code"]: r["wh_name"] for r in q("SELECT wh_code, wh_name FROM dim_warehouses")}
    inv = [{"wh_code": r["wh_code"], "wh_name": wh_name.get(r["wh_code"], r["wh_code"]),
            "actual_qty": r["actual_qty"], "book_qty": r["book_qty"],
            "safety_stock": r["safety_stock"]} for r in fdb.inventory_rows(sku)]
    inbound = [dict(r) for r in fdb.inbound_rows(sku)]
    weekly = [{"week": w, "demand": d} for w, _, d in fdb.demand_series(sku)]
    fc = forecast_demand(sku, 4)
    rep = replenish_tool.calc_replenishment(sku)
    # 预测误差：近 8 周朴素基线(上周值作为本周预测)的 MAPE；周波动系数 CV=σ/水平
    vals = [w["demand"] for w in weekly[-8:]]
    mape = None
    if len(vals) >= 3:
        errs = [abs(vals[i] - vals[i - 1]) / vals[i - 1] for i in range(1, len(vals)) if vals[i - 1] > 0]
        mape = round(sum(errs) / len(errs), 4) if errs else None
    lvl = fc.get("level_per_week") or 0
    sig = fc.get("weekly_volatility_sigma") or 0
    cv = round(sig / lvl, 4) if lvl else None
    lots = q("SELECT wh_code, location, batch_no, lot_qty, expiry_date, status FROM fact_stock_lot WHERE sku=? ORDER BY wh_code, location", (sku,))
    inout = q("SELECT wh_code, io_type, qty, ref_no, ts FROM fact_inout WHERE sku=? ORDER BY ts DESC LIMIT 20", (sku,))
    return {
        "sku": info["sku"], "name": info["name"], "category": info["category"],
        "unit_price": info["unit_price"], "abc_class": info["abc_class"], "xyz_class": info["xyz_class"],
        "supplier": f"{info['supplier_name']}({info['city']})", "on_time_rate": info["on_time_rate"],
        "lead_time_weeks": info["lead_time_weeks"], "moq": info["moq"], "annual_value": info["annual_value"],
        "inventory": inv, "inbound": inbound, "weekly": weekly,
        "forecast": fc.get("forecast", []),
        "replenish": {"available": rep.get("available"), "rop": rep.get("rop"),
                      "safety_stock": rep.get("safety_stock"), "suggested_order_qty": rep.get("suggested_order_qty"),
                      "need_order": rep.get("need_order"), "stockout_week": rep.get("stockout_week_if_no_order"),
                      "service_level": rep.get("service_level")},
        "accuracy": {"mape": mape, "cv": cv},
        "lots": lots, "inout": inout,
    }


def shipment_detail(sid: str):
    s = q1("SELECT * FROM fact_shipments WHERE shipment_id=?", (sid,))
    if not s:
        return {"error": "未找到运单"}
    order = q1("""SELECT o.*, p.name AS product_name, c.cust_name, c.region
                  FROM fact_orders o JOIN dim_products p ON o.sku=p.sku
                  JOIN dim_customers c ON o.cust_id=c.cust_id WHERE o.order_no=?""", (s["order_no"],))
    complaints = q("SELECT * FROM fact_complaints WHERE shipment_id=? OR order_no=?", (sid, s["order_no"]))
    tracking = q("SELECT seq, ts, lng, lat, event FROM fact_tracking WHERE shipment_id=? ORDER BY seq", (sid,))
    freight = q1("SELECT base_fee, fuel_fee, total, settle_status FROM fact_freight WHERE shipment_id=?", (sid,))
    return {"shipment": s, "order": order, "complaints": complaints, "tracking": tracking, "freight": freight}


# ---- AI 计划员（多轮会话，进程内保持）----
_session = None


def ai_session():
    global _session
    if _session is None:
        from agent import AgentSession
        _session = AgentSession()
    return _session


def ai_chat(message: str):
    s = ai_session()
    n0 = len(s.trace)
    answer = s.ask(message)
    trace = [{"tool": t["tool"], "args": t["args"], "head": t.get("result_head", "")[:300]}
             for t in s.trace[n0:]]
    return {"answer": answer, "trace": trace}


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send({"name": "新能源汽车售后供应链 融合平台 API", "endpoints": [
                "GET /api/overview", "GET /api/datasources", "GET /api/shipments",
                "GET /api/shipments/status", "GET /api/tracking/:id", "GET /api/alerts",
                "GET /api/inventory", "GET /api/inventory/summary", "GET /api/orders/trend",
                "POST /api/ai/chat", "POST /api/ai/reset"]})
        if path == "/api/overview":
            return self._send(overview())
        if path == "/api/datasources":
            return self._send(json.loads(DATASOURCES.read_text(encoding="utf-8")))
        if path == "/api/shipments":
            return self._send(shipments())
        if path == "/api/shipments/status":
            return self._send(q("SELECT status, COUNT(*) c FROM fact_shipments GROUP BY status"))
        if path.startswith("/api/shipment/"):
            return self._send(shipment_detail(path.rsplit("/", 1)[-1]))
        if path.startswith("/api/sku/"):
            return self._send(sku_detail(path.rsplit("/", 1)[-1]))
        if path.startswith("/api/tracking/"):
            sid = path.rsplit("/", 1)[-1]
            return self._send(q("SELECT seq, ts, lng, lat, event FROM fact_tracking WHERE shipment_id=? ORDER BY seq", (sid,)))
        if path == "/api/alerts":
            return self._send(alerts())
        if path == "/api/inventory":
            return self._send(inventory())
        if path == "/api/inventory/summary":
            return self._send(inventory_summary())
        if path == "/api/replenishment/proposal":
            return self._send(proposal())
        if path == "/api/skus":
            return self._send(q(
                "SELECT p.sku, p.name, p.category, p.unit_price, sp.abc_class, sp.xyz_class "
                "FROM dim_products p JOIN fact_sku_plan sp ON p.sku=sp.sku ORDER BY p.sku"))
        if path == "/api/forecast/accuracy":
            return self._send(forecast_accuracy())
        if path == "/api/orders":
            return self._send(q(
                "SELECT o.order_no, o.order_date, o.status, o.sku, p.name AS product_name, o.qty, o.amount, "
                "c.cust_name, c.region FROM fact_orders o JOIN dim_products p ON o.sku=p.sku "
                "JOIN dim_customers c ON o.cust_id=c.cust_id ORDER BY o.order_no DESC LIMIT 300"))
        if path == "/api/complaints":
            return self._send(q("SELECT * FROM fact_complaints ORDER BY date DESC"))
        if path == "/api/orders/trend":
            return self._send(q(
                "SELECT dw.week_start AS order_date, SUM(o.qty) AS c "
                "FROM fact_orders o JOIN fact_demand_weekly dw ON o.sku = dw.sku "
                "AND o.order_date >= dw.week_start AND o.order_date < date(dw.week_start, '+7 days') "
                "GROUP BY dw.week ORDER BY dw.week"))
        return self._send({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if path == "/api/ai/chat":
            return self._send(ai_chat(body.get("message", "")))
        if path == "/api/ai/reset":
            global _session
            _session = None
            return self._send({"ok": True})
        return self._send({"error": "not found"}, 404)

    def log_message(self, *args):  # 静默访问日志
        pass


if __name__ == "__main__":
    port = 8503
    print(f"融合平台 API 已启动: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
