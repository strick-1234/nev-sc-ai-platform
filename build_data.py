# -*- coding: utf-8 -*-
"""融合平台 · 一体化数据生成（模拟 5 套系统 → ETL → 数仓 → 导出）

域设定：新能源汽车售后零部件分销供应链（与物流集成平台的表结构/字段风格完全对齐，
并扩展供应商与在途采购等计划决策所需维度）。

生成物：
  data/raw/erp|wms|tms|mes|crm/   5 套系统的原始文件（CSV/JSON，含异构与脏数据）
  data/warehouse.db               统一数仓（平台 11 表 + 计划扩展表）
  data/导出/*.csv                 关键表导出（供报告/演示直接使用）

用法: .venv\Scripts\python.exe 融合平台\build_data.py
"""
from __future__ import annotations

import csv
import json
import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
DB = HERE / "data" / "warehouse.db"
EXP = HERE / "data" / "导出"
RNG = np.random.default_rng(20260906)

# ---------- 公共：城市坐标与月份季节指数 ----------
CITY = {
    "上海": (121.47, 31.23), "广州": (113.26, 23.13), "成都": (104.07, 30.67),
    "武汉": (114.31, 30.59), "西安": (108.94, 34.34), "沈阳": (123.43, 41.80),
    "济南": (117.12, 36.65), "重庆": (106.55, 29.56), "宁德": (119.53, 26.66),
    "苏州": (120.58, 31.30), "杭州": (120.15, 30.28), "常州": (119.97, 31.81),
    "无锡": (120.31, 31.49), "宁波": (121.55, 29.88), "合肥": (117.23, 31.82),
    "南京": (118.80, 32.06), "芜湖": (118.43, 31.35), "北京": (116.41, 39.90),
    "深圳": (114.06, 22.55), "长沙": (112.94, 28.23), "天津": (117.20, 39.08),
}
MONTH_FACTOR = {1: 1.04, 2: 0.66, 3: 1.02, 4: 0.98, 5: 1.00, 6: 1.08,
                7: 0.94, 8: 0.92, 9: 1.06, 10: 1.08, 11: 1.16, 12: 1.14}
MF_MEAN = sum(MONTH_FACTOR.values()) / 12

# ---------- 供应商 ----------
# (id, 名称, 城市, 准时率)
SUPPLIERS = [
    ("S-01", "瑞能电池科技", "宁德", 0.985), ("S-02", "恒动电驱系统", "苏州", 0.978),
    ("S-03", "智芯微电子", "杭州", 0.960), ("S-04", "安驰结构件", "常州", 0.982),
    ("S-05", "联发线束", "无锡", 0.975), ("S-06", "骏驰零部件", "芜湖", 0.970),
    ("S-07", "光迅车灯", "宁波", 0.980), ("S-08", "安座汽车内饰", "合肥", 0.972),
    ("S-09", "锐普转向系统", "武汉", 0.955), ("S-10", "青能车载电源", "南京", 0.988),
]
# ---------- 30 个售后零部件（主角，保持稳定供演示） ----------
# (sku, 名称, 类别, 单价, xyz, 供应商, 提前期周, 周均需求μ)
HERO_PARTS = [
    ("SKU0001", "动力电芯总成", "三电系统", 4200, "X", "S-01", 2, 620),
    ("SKU0002", "电池包壳体", "三电系统", 900, "Y", "S-04", 2, 900),
    ("SKU0003", "驱动电机总成", "三电系统", 4500, "X", "S-02", 3, 210),
    ("SKU0004", "车载充电机", "三电系统", 1600, "Y", "S-10", 2, 520),
    ("SKU0005", "电机逆变器", "三电系统", 3200, "Y", "S-02", 3, 260),
    ("SKU0006", "电池管理主板", "电子电器", 1200, "Y", "S-03", 2, 200),
    ("SKU0007", "电动助力转向机", "底盘与转向", 2100, "Z", "S-09", 3, 170),
    ("SKU0008", "高压线束总成", "电子电器", 650, "X", "S-05", 1, 420),
    ("SKU0009", "前大灯总成", "电子电器", 480, "X", "S-07", 2, 560),
    ("SKU0010", "座椅骨架", "车身附件", 400, "X", "S-08", 2, 560),
    ("SKU0011", "全景天窗玻璃", "车身附件", 300, "Y", "S-08", 2, 520),
    ("SKU0012", "低滚阻轮胎", "底盘与转向", 550, "X", "S-06", 1, 200),
    ("SKU0013", "前后保险杠", "车身附件", 350, "Y", "S-06", 2, 280),
    ("SKU0014", "毫米波雷达", "电子电器", 260, "Y", "S-03", 1, 180),
    ("SKU0015", "环视摄像头", "电子电器", 150, "X", "S-03", 1, 160),
    ("SKU0016", "电子水泵", "底盘与转向", 120, "Y", "S-05", 1, 150),
    ("SKU0017", "冷却管路组件", "底盘与转向", 45, "X", "S-05", 1, 400),
    ("SKU0018", "空调滤芯", "车身附件", 30, "X", "S-05", 1, 300),
    ("SKU0019", "标准紧固件(套)", "标准件", 8, "X", "S-06", 1, 2500),
    ("SKU0020", "高压接触器", "电子电器", 90, "Z", "S-03", 2, 90),
    ("SKU0021", "交流充电枪总成", "三电系统", 280, "X", "S-10", 1, 240),
    ("SKU0022", "热泵压缩机", "三电系统", 2400, "Y", "S-10", 3, 90),
    ("SKU0023", "前制动卡钳", "底盘与转向", 620, "Y", "S-06", 2, 130),
    ("SKU0024", "前制动片(套)", "底盘与转向", 120, "X", "S-06", 1, 400),
    ("SKU0025", "雨刮电机", "车身附件", 90, "X", "S-07", 1, 260),
    ("SKU0026", "车窗升降电机", "车身附件", 75, "Y", "S-07", 1, 210),
    ("SKU0027", "中控显示屏", "电子电器", 1800, "Z", "S-03", 3, 60),
    ("SKU0028", "空气悬架气泵", "底盘与转向", 850, "Y", "S-09", 3, 70),
    ("SKU0029", "冷却液壶", "底盘与转向", 25, "X", "S-05", 1, 900),
    ("SKU0030", "碳罐", "底盘与转向", 65, "Z", "S-09", 2, 55),
]

N_SKU = 3000


def _gen_parts():
    """在 30 个主角之上程序化生成到 N_SKU 个 SKU（独立随机种子，不影响主角数据）。"""
    rng = np.random.default_rng(20260906)
    families = [
        ("三电系统", ["动力电池模组", "电控单元", "车载充电模块", "高压配电盒", "电池热管理组件"], (300, 5000)),
        ("电子电器", ["低压线束", "域控制器", "毫米波传感器", "环视摄像头", "前照灯总成", "中控屏组件"], (50, 2000)),
        ("底盘与转向", ["转向节", "制动钳", "悬架弹簧", "副车架", "传动半轴", "轮毂单元"], (100, 3000)),
        ("车身附件", ["座椅骨架", "车门玻璃", "保险杠", "仪表台", "顶棚内衬", "密封条"], (30, 800)),
        ("标准件", ["紧固件", "卡扣", "垫圈", "油封", "线夹"], (1, 30)),
    ]
    parts = list(HERO_PARTS)
    for i in range(31, N_SKU + 1):
        cat, bases, (lo, hi) = families[rng.integers(0, len(families))]
        name = f"{bases[rng.integers(0, len(bases))]}{rng.integers(10, 99)}"
        price = int(round(float(rng.uniform(lo, hi))))
        xyz = str(rng.choice(["X", "Y", "Z"], p=[0.45, 0.35, 0.20]))
        supplier = f"S-{rng.integers(1, 11):02d}"
        lead = int(rng.integers(1, 4))
        mu = max(1, int(round(10 ** float(rng.uniform(0, 3.5)))))
        parts.append((f"SKU{i:04d}", name, cat, price, xyz, supplier, lead, mu))
    return parts


PARTS = _gen_parts()
MU = {p[0]: p[7] for p in PARTS}
PRICE = {p[0]: p[3] for p in PARTS}
XYZ = {p[0]: p[4] for p in PARTS}
SUP = {p[0]: (p[5], p[6]) for p in PARTS}   # sku -> (supplier, lead)
MOQ = {p[0]: max(50, int(math.ceil(p[7] / 50.0)) * 50) for p in PARTS}

# ---------- 仓库 / 客户 ----------
# (wh_code, 名称, 城市, 区域)  8 个区域备件中心仓
WAREHOUSES = [
    ("WH001", "华东备件中心仓(上海)", "上海", "华东"), ("WH002", "华南备件中心仓(广州)", "广州", "华南"),
    ("WH003", "西南备件中心仓(成都)", "成都", "西南"), ("WH004", "华中备件中心仓(武汉)", "武汉", "华中"),
    ("WH005", "西北备件中心仓(西安)", "西安", "西北"), ("WH006", "东北备件中心仓(沈阳)", "沈阳", "东北"),
    ("WH007", "华北备件中心仓(济南)", "济南", "华北"), ("WH008", "重庆前置仓", "重庆", "西南"),
]
REGION_CITIES = {
    "华东": ["上海", "南京", "杭州", "宁波"], "华南": ["广州", "深圳"], "西南": ["成都", "重庆"],
    "华中": ["武汉", "长沙"], "西北": ["西安"], "东北": ["沈阳"], "华北": ["北京", "济南", "天津"],
}
CITIES = list(CITY.keys())

# ---------- 工具函数 ----------
def hav(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    return 2 * r * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)) * 1.3


def weeks52() -> list[tuple[int, date]]:
    # 52 周，最近一周结束在“今天”附近（以 2026-09-06 为当前周）
    last_start = date(2026, 8, 31)
    return [(52 - i, last_start - timedelta(weeks=i)) for i in range(51, -1, -1)]


def clean_num(v):
    return int(round(float(v)))


# ============================================================
# 1) 生成 5 套系统原始文件（保留异构特征：中文状态、驼峰/下划线混杂、个别脏数据）
# ============================================================
def gen_raw():
    if RAW.exists():
        import shutil
        shutil.rmtree(RAW)
    for d in ["erp", "wms", "tms", "mes", "crm"]:
        (RAW / d).mkdir(parents=True)

    # --- ERP（CSV，老旧系统）---
    with open(RAW / "erp" / "products.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sku", "name", "category", "unitPrice", "spec"])
        for p in PARTS:
            w.writerow([p[0], p[1], p[2], p[3], "件"])
    customers = []
    grade_regions = {"A": ["华东", "华南", "华北"], "B": ["华东", "华南", "华中", "西南"], "C": ["西北", "东北", "西南"]}
    for i in range(40):
        grade = "A" if i < 8 else ("B" if i < 24 else "C")
        region = RNG.choice(grade_regions[grade])
        cid = f"C{i + 1:04d}"
        customers.append({"custId": cid, "custName": f"{region}新能售后{i + 1:02d}号服务站",
                          "region": region, "grade": grade, "tel": f"13{RNG.integers(100000000, 999999999)}"})
    with open(RAW / "erp" / "customers.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["custId", "custName", "region", "grade", "tel"])
        for c in customers:
            w.writerow([c["custId"], c["custName"], c["region"], c["grade"], c["tel"]])
    with open(RAW / "erp" / "suppliers.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["supplierId", "supplierName", "city", "onTimeRate"])
        for s in SUPPLIERS:
            w.writerow([s[0], s[1], s[2], s[3]])

    # --- WMS（JSON API）---
    wh_list = [{"whCode": w[0], "whName": w[1], "region": w[3],
                "capacity": int(RNG.integers(80000, 180000)), "used": 0} for w in WAREHOUSES]
    inv_rows = []
    for p in PARTS:
        sku = p[0]
        if sku == "SKU0001":
            n_wh, whs = 1, np.array([0])          # 主角：仅上海仓且低库存
        elif sku == "SKU0003":
            n_wh, whs = 4, None
        elif XYZ[sku] == "Z":
            n_wh, whs = 1, None
        else:
            n_wh, whs = int(RNG.integers(1, 4)), None
        if whs is None:
            whs = RNG.choice(len(WAREHOUSES), size=n_wh, replace=False)
        for wi in whs:
            w = WAREHOUSES[int(wi)]
            safety = max(10, clean_num(MU[sku] * SUP[sku][1] * 0.5))
            if sku == "SKU0001" and w[0] == "WH001":  # 主角：库存告急
                actual, book = 180, 180
            else:
                actual = safety + clean_num(MU[sku] * RNG.uniform(0.3, 1.8))
                book = actual if RNG.random() < 0.8 else actual + int(RNG.integers(-8, 9))
            inv_rows.append({"whCode": w[0], "sku": sku, "bookQty": book, "actualQty": actual,
                             "safetyStock": safety,
                             "lastCheck": (date(2026, 8, 31) - timedelta(days=int(RNG.integers(0, 14)))).isoformat()})
    with open(RAW / "wms" / "warehouses.json", "w", encoding="utf-8") as f:
        json.dump(wh_list, f, ensure_ascii=False, indent=1)
    with open(RAW / "wms" / "inventory.json", "w", encoding="utf-8") as f:
        json.dump(inv_rows, f, ensure_ascii=False, indent=1)

    # --- 订单（52 周销售历史）---
    wk = weeks52()
    orders = []
    seq = 260001
    oid = 1
    order_city = {}  # orderNo -> dest city
    cust_of = {c["custId"]: c for c in customers}
    cust_ids = [c["custId"] for c in customers]
    for wno, wstart in wk:
        m = wstart.month
        season = MONTH_FACTOR[m] / MF_MEAN
        trend = 1.0 + 0.10 * (52 - wno) / 51
        for p in PARTS:
            sku = p[0]
            base = MU[sku] * season * trend
            if XYZ[sku] == "X":
                qty = max(0, int(RNG.normal(base, base * 0.12)))
            elif XYZ[sku] == "Y":
                qty = max(0, int(RNG.normal(base, base * 0.30)))
            else:
                qty = 0 if RNG.random() > 0.28 else max(1, int(base * RNG.lognormal(0, 0.6) / 0.28))
            if qty == 0:
                continue
            cust = cust_of[RNG.choice(cust_ids)]
            order_date = wstart + timedelta(days=int(RNG.integers(0, 6)))
            age_days = (date(2026, 8, 31) - order_date).days
            if age_days > 21:
                status = "已完成"
            elif age_days > 7:
                status = "已完成" if RNG.random() < 0.75 else "已发货"
            else:
                r = RNG.random()
                status = "待发货" if r < 0.35 else ("已发货" if r < 0.9 else "已完成")
            if RNG.random() < 0.02 and age_days < 30:
                status = "已取消"
            order_no = f"SO{seq}"
            seq += 1
            orders.append({
                "orderId": oid, "orderNo": order_no, "custId": cust["custId"],
                "sku": sku, "qty": qty, "amount": round(qty * PRICE[sku], 2),
                "orderDate": order_date.isoformat(), "status": status,
                "week": wno, "region": cust["region"],
            })
            oid += 1
            order_city[order_no] = RNG.choice(REGION_CITIES[cust["region"]])
    with open(RAW / "erp" / "orders.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["orderNo", "custId", "sku", "qty", "amount", "orderDate", "status"])
        for o in orders:
            w.writerow([o["orderNo"], o["custId"], o["sku"], o["qty"], o["amount"], o["orderDate"], o["status"]])
    # ERP 采购订单（在途扩展：供应商 → 中心仓）
    pos = []
    pseq = 1
    for p in PARTS:
        sku = p[0]
        if sku == "SKU0001" or RNG.random() < 0.75:
            continue
        qty = clean_num(MU[sku] * SUP[sku][1] * RNG.uniform(0.5, 1.3))
        pos.append({"poId": f"PO26{pseq:05d}", "sku": sku, "supplierId": SUP[sku][0],
                    "qty": max(MOQ[sku], qty), "etaWeek": int(RNG.integers(1, 3)),
                    "status": "在途", "orderDate": "2026-08-25"})
        pseq += 1
    with open(RAW / "erp" / "purchase_orders.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["poId", "sku", "supplierId", "qty", "etaWeek", "status", "orderDate"])
        for po in pos:
            w.writerow([po["poId"], po["sku"], po["supplierId"], po["qty"], po["etaWeek"], po["status"], po["orderDate"]])

    # --- TMS（JSON API + GPS）---
    carriers = ["京东物流", "顺丰供应链", "安得智联", "德邦物流", "中通快运"]
    vehicles = []
    for i in range(20):
        city = RNG.choice(list(CITY.keys()))
        vehicles.append({"vehicleId": f"V{i + 1:03d}", "plate": f"沪A{RNG.integers(10000, 99999)}",
                         "driver": f"{RNG.choice(['张', '李', '王', '赵', '刘', '陈'])}师傅",
                         "carrier": RNG.choice(carriers), "capacity": float(RNG.integers(8, 32)),
                         "status": "运输中" if RNG.random() < 0.4 else "空闲"})
    with open(RAW / "tms" / "vehicles.json", "w", encoding="utf-8") as f:
        json.dump(vehicles, f, ensure_ascii=False, indent=1)
    # 运单：待发货订单→待发运；已发货/已完成→在途/已签收/异常（有延迟即异常）
    def age_days(o):
        return (date(2026, 9, 6) - date.fromisoformat(o["orderDate"])).days
    pending = [o for o in orders if o["status"] == "待发货" and age_days(o) <= 7][:200]
    recent = [o for o in orders if o["status"] in ("已发货", "已完成") and age_days(o) <= 40]
    RNG.shuffle(recent)
    recent = recent[:1000]
    shipments, tracking = [], []
    hid, tid = 260001, 1
    for o in pending + recent:
        dest = order_city.get(o["orderNo"], RNG.choice(CITIES))
        region = next((c["region"] for c in customers if c["custId"] == o["custId"]), "华东")
        wh = next((w for w in WAREHOUSES if w[3] == region), WAREHOUSES[0])
        origin = wh[2]
        depart = date.fromisoformat(o["orderDate"]) + timedelta(days=1)
        (lo1, la1), (lo2, la2) = CITY[origin], CITY[dest]
        dist = clean_num(hav(la1, lo1, la2, lo2))
        age = (date(2026, 9, 6) - depart).days
        if o["status"] == "待发货":
            status, delay, exc = "待发运", 0, ""
        else:
            delay = int(RNG.integers(30, 400)) if RNG.random() < 0.22 else 0
            exc = "" if delay == 0 else RNG.choice(["延迟", "延迟", "路况异常"])
            status = "异常" if delay > 0 else ("已签收" if age >= 3 else "在途")
        eta = depart + timedelta(days=1)
        progress = 1.0 if status == "已签收" else (0.0 if status == "待发运" else RNG.uniform(0.25, 0.9))
        clng = lo1 + (lo2 - lo1) * progress
        clat = la1 + (la2 - la1) * progress
        sid = f"TN26{hid}"
        hid += 1
        shipments.append({"shipmentId": sid, "orderRef": o["orderNo"], "vehicleId": RNG.choice(vehicles)["vehicleId"],
                          "carrier": RNG.choice(carriers), "origin": origin, "dest": dest, "distance": dist,
                          "status": status, "progress": round(progress, 3), "currentLng": round(clng, 4),
                          "currentLat": round(clat, 4),
                          "departTime": f"{depart.isoformat()} 06:40",
                          "eta": f"{(depart + timedelta(days=1)).isoformat()} 18:00",
                          "delayMin": delay, "exceptionType": exc})
        n_pts = 10 if status == "已签收" else (2 if status == "待发运" else 8)
        for k in range(n_pts + 1):
            t = k / n_pts
            ts_dt = depart + timedelta(hours=int(8 + t * 20))
            event = "发车" if k == 0 else ("签收" if k == n_pts else "在途")
            tracking.append({"shipmentId": sid, "seq": k, "ts": ts_dt.isoformat()[:16],
                             "lng": round(lo1 + (lo2 - lo1) * t, 4), "lat": round(la1 + (la2 - la1) * t, 4),
                             "event": event})
            tid += 1
    with open(RAW / "tms" / "shipments.json", "w", encoding="utf-8") as f:
        json.dump(shipments, f, ensure_ascii=False, indent=1)
    with open(RAW / "tms" / "tracking.json", "w", encoding="utf-8") as f:
        json.dump(tracking, f, ensure_ascii=False, indent=1)

    # --- MES（CSV）---
    with open(RAW / "mes" / "production.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["workOrder", "sku", "line", "plannedQty", "actualQty", "passRate", "produceDate"])
        wo = 260001
        for p in PARTS:
            sku = p[0]
            for _ in range(int(RNG.integers(3, 6))):
                planned = clean_num(MU[sku] * RNG.uniform(2, 5))
                actual = clean_num(planned * RNG.uniform(0.92, 1.0))
                pass_rate = round(RNG.uniform(92.0, 98.5), 1)
                d = date(2026, 7, 1) + timedelta(days=int(RNG.integers(0, 55)))
                w.writerow([f"WO{wo}", sku, RNG.choice(["A线", "B线", "C线"]), planned, actual,
                            pass_rate, d.isoformat()])
                wo += 1

    # --- CRM（JSON API）---
    comp_types = ["延迟", "破损", "丢件", "服务态度", "账单争议"]
    complaints = []
    cp = 260001
    for i in range(150):
        c = RNG.choice(customers)
        has_ship = shipments[int(RNG.integers(0, len(shipments)))] if shipments else None
        typ = RNG.choice(comp_types)
        complaints.append({
            "complaintId": f"CP{cp}", "custId": c["custId"],
            "orderNo": has_ship["orderRef"] if has_ship else "",
            "shipmentId": has_ship["shipmentId"] if has_ship else "",
            "type": typ, "satisfaction": int(RNG.integers(1, 6)),
            "date": (date(2026, 8, 5) + timedelta(days=int(RNG.integers(0, 30)))).isoformat(),
            "handled": bool(RNG.random() < 0.7)})
        cp += 1
    with open(RAW / "crm" / "complaints.json", "w", encoding="utf-8") as f:
        json.dump(complaints, f, ensure_ascii=False, indent=1)
    with open(RAW / "datasources.json", "w", encoding="utf-8") as f:
        json.dump([
            {"id": "erp", "name": "ERP 企业资源计划", "format": "CSV 文件导出", "update": "每天 02:00 批量",
             "access": "文件导出(人工/定时)", "records": len(orders) + 40 + 30, "status": "正常",
             "note": "老旧系统，字段不规范，需人工导出"},
            {"id": "wms", "name": "WMS 仓储管理", "format": "JSON API", "update": "实时", "access": "REST API",
             "records": len(inv_rows), "status": "正常", "note": ""},
            {"id": "tms", "name": "TMS 运输管理(含 GPS)", "format": "JSON API", "update": "5 分钟",
             "access": "REST API", "records": len(shipments), "status": "正常", "note": ""},
            {"id": "mes", "name": "MES 制造执行", "format": "CSV 文件导出", "update": "每小时", "access": "文件导出",
             "records": wo - 260001, "status": "正常", "note": ""},
            {"id": "crm", "name": "CRM 客户关系管理", "format": "JSON API", "update": "实时", "access": "REST API",
             "records": len(complaints), "status": "正常", "note": ""},
        ], f, ensure_ascii=False, indent=1)
    print(f"[1/3] 原始数据生成完成: 订单 {len(orders)} | 库存 {len(inv_rows)} | 运单 {len(shipments)} | 轨迹 {len(tracking)} | 投诉 {len(complaints)}")
    return orders, inv_rows, shipments, tracking, complaints, customers


# ============================================================
# 2) ETL：清洗 → 数仓（平台 11 表 + 计划扩展表）
# ============================================================
def build_dw(orders, inv_rows, shipments, tracking, complaints, customers):
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE dim_products(sku TEXT PRIMARY KEY, name TEXT, category TEXT, unit_price REAL);
    CREATE TABLE dim_customers(cust_id TEXT PRIMARY KEY, cust_name TEXT, region TEXT, grade TEXT);
    CREATE TABLE dim_warehouses(wh_code TEXT PRIMARY KEY, wh_name TEXT, region TEXT, capacity REAL);
    CREATE TABLE dim_vehicles(vehicle_id TEXT PRIMARY KEY, plate TEXT, driver TEXT, carrier TEXT, capacity REAL, status TEXT);
    CREATE TABLE fact_orders(order_id INTEGER PRIMARY KEY, order_no TEXT, cust_id TEXT, sku TEXT, qty INTEGER, amount REAL, order_date TEXT, status TEXT);
    CREATE TABLE fact_inventory(id INTEGER PRIMARY KEY AUTOINCREMENT, wh_code TEXT, sku TEXT, book_qty INTEGER, actual_qty INTEGER, safety_stock INTEGER, diff_qty INTEGER, last_check TEXT);
    CREATE TABLE fact_shipments(shipment_id TEXT PRIMARY KEY, order_no TEXT, vehicle_id TEXT, carrier TEXT, origin TEXT, dest TEXT, distance REAL, status TEXT, progress REAL, lng REAL, lat REAL, depart_time TEXT, eta TEXT, delay_min INTEGER, exception_type TEXT);
    CREATE TABLE fact_tracking(id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id TEXT, seq INTEGER, ts TEXT, lng REAL, lat REAL, event TEXT);
    CREATE TABLE fact_production(work_order TEXT PRIMARY KEY, sku TEXT, line TEXT, planned_qty INTEGER, actual_qty INTEGER, pass_rate REAL, produce_date TEXT);
    CREATE TABLE fact_complaints(complaint_id TEXT PRIMARY KEY, cust_id TEXT, order_no TEXT, shipment_id TEXT, type TEXT, satisfaction INTEGER, date TEXT, handled INTEGER);
    CREATE TABLE fact_alerts(alert_id TEXT PRIMARY KEY, source TEXT, ref_id TEXT, type TEXT, level TEXT, description TEXT, status TEXT, create_time TEXT);
    -- 计划决策扩展（供应商 / 分仓在途 / 周需求 / SKU 策略）
    CREATE TABLE dim_suppliers(supplier_id TEXT PRIMARY KEY, name TEXT, city TEXT, lat REAL, lon REAL, on_time_rate REAL);
    CREATE TABLE fact_inbound(po_id TEXT PRIMARY KEY, sku TEXT, supplier_id TEXT, qty INTEGER, eta_week INTEGER, status TEXT);
    CREATE TABLE fact_demand_weekly(sku TEXT, week INTEGER, week_start TEXT, demand INTEGER, PRIMARY KEY(sku, week));
    CREATE TABLE fact_sku_plan(sku TEXT PRIMARY KEY, abc_class TEXT, xyz_class TEXT, annual_value REAL, supplier_id TEXT, lead_time_weeks INTEGER, moq INTEGER);
    CREATE TABLE fact_stock_lot(id INTEGER PRIMARY KEY AUTOINCREMENT, wh_code TEXT, sku TEXT, location TEXT, batch_no TEXT, lot_qty INTEGER, expiry_date TEXT, status TEXT);
    CREATE TABLE fact_inout(id INTEGER PRIMARY KEY AUTOINCREMENT, wh_code TEXT, sku TEXT, io_type TEXT, qty INTEGER, ref_no TEXT, ts TEXT);
    CREATE TABLE fact_freight(shipment_id TEXT PRIMARY KEY, base_fee REAL, fuel_fee REAL, total REAL, settle_status TEXT);
    """)
    cur = con.cursor()
    # 维度
    for p in PARTS:
        cur.execute("INSERT INTO dim_products VALUES(?,?,?,?)", (p[0], p[1], p[2], p[3]))
    for c in customers:
        cur.execute("INSERT INTO dim_customers VALUES(?,?,?,?)", (c["custId"], c["custName"], c["region"], c["grade"]))
    for w in WAREHOUSES:
        cur.execute("INSERT INTO dim_warehouses VALUES(?,?,?,?)", (w[0], w[1], w[3], 100000.0))
    for s in SUPPLIERS:
        la, lo = CITY[s[2]][1], CITY[s[2]][0]
        cur.execute("INSERT INTO dim_suppliers VALUES(?,?,?,?,?,?)", (s[0], s[1], s[2], la, lo, s[3]))
    # 事实：订单（清洗：剔除取消/无效客户行）
    dropped = 0
    for o in orders:
        if o["status"] == "已取消":
            dropped += 1
            continue
        cur.execute("INSERT INTO fact_orders(order_id,order_no,cust_id,sku,qty,amount,order_date,status) VALUES(?,?,?,?,?,?,?,?)",
                    (o["orderId"], o["orderNo"], o["custId"], o["sku"], o["qty"], o["amount"], o["orderDate"],
                     {"已完成": "completed", "已发货": "shipped", "待发货": "pending"}[o["status"]]))
    for r in inv_rows:
        cur.execute("INSERT INTO fact_inventory(wh_code,sku,book_qty,actual_qty,safety_stock,diff_qty,last_check) VALUES(?,?,?,?,?,?,?)",
                    (r["whCode"], r["sku"], r["bookQty"], r["actualQty"], r["safetyStock"],
                     r["bookQty"] - r["actualQty"], r["lastCheck"]))

    # ---- WMS 明细层：库位/批次/效期 ----
    expiry_alert_rows = []
    today = date(2026, 9, 6)
    for r in inv_rows:
        wh, sku, actual = r["whCode"], r["sku"], r["actualQty"]
        rem, n = actual, (1 if actual <= 60 else int(RNG.integers(1, 4)))
        for k in range(n):
            qty = rem if k == n - 1 else max(1, int(rem * RNG.uniform(0.3, 0.6)))
            rem -= qty
            loc = f"{wh}-A-{RNG.integers(1, 10):02d}-{RNG.integers(1, 30):02d}"
            batch = f"BT{wh[2:]}-{sku}-{k + 1}"
            exp = None
            if RNG.random() < 0.35:
                exp = (today + timedelta(days=int(RNG.integers(20, 400)))).isoformat()
                left = (date.fromisoformat(exp) - today).days
                if left <= 60:
                    expiry_alert_rows.append((batch, f"批次 {batch} 效期 {exp}（剩 {left} 天）"))
            status = "冻结" if RNG.random() < 0.05 else "正常"
            cur.execute("INSERT INTO fact_stock_lot(wh_code,sku,location,batch_no,lot_qty,expiry_date,status) VALUES(?,?,?,?,?,?,?)",
                        (wh, sku, loc, batch, qty, exp, status))
    # ---- 出入库流水（近 8 周）----
    for p in PARTS:
        sku = p[0]
        wh = RNG.choice(WAREHOUSES)[0]
        for _ in range(int(RNG.integers(4, 9))):
            io = RNG.choice(["入库", "出库"])
            qty = clean_num(MU[sku] * RNG.uniform(0.3, 1.5))
            ts = (date(2026, 7, 1) + timedelta(days=int(RNG.integers(0, 60)))).isoformat() + " 09:00"
            ref = f"PO26{RNG.integers(10000, 99999)}" if io == "入库" else f"SO26{RNG.integers(10000, 99999)}"
            cur.execute("INSERT INTO fact_inout(wh_code,sku,io_type,qty,ref_no,ts) VALUES(?,?,?,?,?,?)",
                        (wh, sku, io, qty, ref, ts))
    # ---- 运费结算（TMS 成本）----
    for s in shipments:
        base = round(s["distance"] * 3.2 + 180, 2)
        fuel = round(s["distance"] * 0.55, 2)
        total = round(base + fuel, 2)
        settle = RNG.choice(["已结算", "待结算"])
        cur.execute("INSERT INTO fact_freight VALUES(?,?,?,?,?)", (s["shipmentId"], base, fuel, total, settle))
    for s in shipments:
        cur.execute("""INSERT INTO fact_shipments(shipment_id,order_no,vehicle_id,carrier,origin,dest,distance,status,progress,lng,lat,depart_time,eta,delay_min,exception_type)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (s["shipmentId"], s["orderRef"], s["vehicleId"], s["carrier"], s["origin"], s["dest"],
                     s["distance"], s["status"], s["progress"], s["currentLng"], s["currentLat"],
                     s["departTime"], s["eta"], s["delayMin"], s["exceptionType"]))
    for t in tracking:
        cur.execute("INSERT INTO fact_tracking(shipment_id,seq,ts,lng,lat,event) VALUES(?,?,?,?,?,?)",
                    (t["shipmentId"], t["seq"], t["ts"], t["lng"], t["lat"], t["event"]))
    # MES / CRM
    with open(RAW / "mes" / "production.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cur.execute("INSERT INTO fact_production VALUES(?,?,?,?,?,?,?)",
                        (row["workOrder"], row["sku"], row["line"], int(row["plannedQty"]), int(row["actualQty"]),
                         float(row["passRate"]), row["produceDate"]))
    for c in complaints:
        cur.execute("INSERT INTO fact_complaints VALUES(?,?,?,?,?,?,?,?)",
                    (c["complaintId"], c["custId"], c["orderNo"], c["shipmentId"], c["type"], c["satisfaction"],
                     c["date"], int(c["handled"])))
    # 周需求（按销售订单聚合）
    weekly = {}
    for o in orders:
        if o["status"] == "已取消":
            continue
        weekly[(o["sku"], o["week"])] = weekly.get((o["sku"], o["week"]), 0) + o["qty"]
    wk = weeks52()
    for p in PARTS:
        sku = p[0]
        for wno, wstart in wk:
            cur.execute("INSERT INTO fact_demand_weekly VALUES(?,?,?,?)",
                        (sku, wno, wstart.isoformat(), weekly.get((sku, wno), 0)))
    # SKU 策略（ABC 由年销售额累计占比定，XYZ 沿用主数据）
    annual = {p[0]: MU[p[0]] * 52 * PRICE[p[0]] for p in PARTS}
    ranked = sorted(annual, key=lambda k: -annual[k])
    total = sum(annual.values())
    cum, abc = 0.0, {}
    for k in ranked:
        cum += annual[k] / total
        abc[k] = "A" if cum <= 0.75 else ("B" if cum <= 0.95 else "C")
    for p in PARTS:
        sku = p[0]
        cur.execute("INSERT INTO fact_sku_plan VALUES(?,?,?,?,?,?,?)",
                    (sku, abc[sku], XYZ[sku], round(annual[sku], 2), SUP[sku][0], SUP[sku][1], MOQ[sku]))
    # 在途采购
    with open(RAW / "erp" / "purchase_orders.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cur.execute("INSERT INTO fact_inbound VALUES(?,?,?,?,?,?)",
                        (row["poId"], row["sku"], row["supplierId"], int(row["qty"]), int(row["etaWeek"]), row["status"]))
    # 告警（ETL 自动派生）
    alerts = []
    a = 1
    def add_alert(source, ref, typ, level, desc):
        nonlocal a
        alerts.append((f"AL{a:06d}", source, ref, typ, level, desc,
                       RNG.choice(["待处理", "处理中", "已闭环"]),
                       (date(2026, 8, 31) + timedelta(days=int(RNG.integers(0, 6)))).isoformat()))
        a += 1
    for s in shipments:
        if s["delayMin"] > 0:
            add_alert("tms", s["shipmentId"], "延迟预警", "高" if s["delayMin"] > 180 else "中",
                      f"{s['shipmentId']} 从 {s['origin']} 到 {s['dest']} 预计延迟 {s['delayMin']} 分钟")
    for r in inv_rows:
        book, actual = r["bookQty"], r["actualQty"]
        if book != actual and abs(book - actual) / max(book, 1) > 0.08:
            add_alert("wms", f"{r['whCode']}-{r['sku']}", "库存差异", "低",
                      f"{r['whCode']} 的 {r['sku']} 账面 {book} ≠ 实际 {actual}")
        if actual < r["safetyStock"] * 0.7:
            add_alert("wms", f"{r['whCode']}-{r['sku']}", "缺货预警", "高",
                      f"{r['whCode']} 的 {r['sku']} 实际库存 {actual} 远低于安全库存 {r['safetyStock']}")
    for c in complaints:
        if c["type"] in ("破损", "丢件"):
            add_alert("crm", c["complaintId"], "丢件" if c["type"] == "丢件" else "破损",
                      "中", f"投诉 {c['complaintId']}: {c['type']} (满意度 {c['satisfaction']})")
    for batch, desc in expiry_alert_rows:
        add_alert("wms", batch, "临期预警", "中", desc)
    # 控制告警总量（保留各等级代表性，避免前端一次渲染上千条）
    alerts = ([a for a in alerts if a[4] == "高"][:120]
              + [a for a in alerts if a[4] == "中"][:80]
              + [a for a in alerts if a[4] == "低"][:50])
    for al in alerts:
        cur.execute("INSERT INTO fact_alerts VALUES(?,?,?,?,?,?,?,?)", al)
    # 索引（放大数据后聚合/下钻性能）
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_orders_date ON fact_orders(order_date)",
        "CREATE INDEX IF NOT EXISTS idx_orders_sku ON fact_orders(sku)",
        "CREATE INDEX IF NOT EXISTS idx_dw_week ON fact_demand_weekly(week)",
        "CREATE INDEX IF NOT EXISTS idx_inv_wh ON fact_inventory(wh_code)",
        "CREATE INDEX IF NOT EXISTS idx_inv_sku ON fact_inventory(sku)",
        "CREATE INDEX IF NOT EXISTS idx_ship_status ON fact_shipments(status)",
        "CREATE INDEX IF NOT EXISTS idx_track_ship ON fact_tracking(shipment_id, seq)",
        "CREATE INDEX IF NOT EXISTS idx_lot_sku ON fact_stock_lot(sku)",
        "CREATE INDEX IF NOT EXISTS idx_inout_sku ON fact_inout(sku, ts)",
        "CREATE INDEX IF NOT EXISTS idx_freight_ship ON fact_freight(shipment_id)",
    ]:
        cur.execute(idx)
    con.commit()
    con.close()
    print(f"[2/3] 数仓生成: {len(alerts)} 条告警(ETL派生) | 剔除取消订单 {dropped} 行")
    return alerts


# ============================================================
# 3) 导出 CSV（交付数据包）
# ============================================================
def export():
    con = sqlite3.connect(DB)
    tables = {
        "dim_products": "商品维度", "dim_customers": "客户维度", "dim_suppliers": "供应商维度",
        "fact_orders": "销售订单", "fact_inventory": "库存(分仓)", "fact_demand_weekly": "周需求序列",
        "fact_sku_plan": "SKU计划策略(ABC-XYZ)", "fact_shipments": "运单", "fact_alerts": "异常告警",
        "fact_complaints": "客户投诉", "fact_stock_lot": "库存批次明细", "fact_inout": "出入库流水",
        "fact_freight": "运单运费结算",
    }
    for t, label in tables.items():
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        rows = con.execute(f"SELECT * FROM {t}").fetchall()
        with open(EXP / f"{label}_{t}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
    con.close()
    n = len(list(EXP.glob("*.csv")))
    print(f"[3/3] 导出完成: data/导出/ 共 {n} 个 CSV")


def main():
    print("== 融合平台数据生成 ==")
    orders, inv, ships, track, comps, custs = gen_raw()
    build_dw(orders, inv, ships, track, comps, custs)
    export()
    print(f"完成。数据库: {DB}")


if __name__ == "__main__":
    main()
