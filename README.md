# 🚛 NEV Aftersales Supply Chain — Data + AI Decision Platform

> **新能源汽车售后供应链「数据 + AI 决策平台」** · 
> 物流数据集成（5 套异构系统 → ETL → 数仓） × 可视化大屏 × LLM Agent 智能决策（AI 计划员）

An all-in-one demo that turns messy heterogeneous logistics data into a decision-support pipeline: **集成 → 建仓 → 可视化 → 对话式 AI 决策 → 审批闭环**。Data is simulated but business-calibrated (deterministic seed, one-command rebuild). No real enterprise data involved.

> 入口为 Vue3 + ECharts 指挥大屏（含全国在途地图、三级详情下钻、补货建议单审批与导出），右侧为 DeepSeek Function Calling 智能体——**所有计算走本地可审计工具，LLM 只做语义理解与编排（防幻觉设计）**。

---

## ✨ 功能亮点

| 层 | 能力 |
|---|---|
| **数据底座** | 模拟 ERP/WMS/TMS/MES/CRM 五套异构系统（CSV/JSON 混杂、字段不一致）→ ETL → 数仓 **18 张业务表**：3,000 SKU × 52 周销售订单 13 万条、GPS 轨迹 1.1 万点、库位批次 8,622、出入库流水 1.8 万、运费、ETL 派生告警（分级+闭环） |
| **可视化大屏** | Vue3 + ECharts 深色指挥大屏：全国在途轨迹地图、告警闭环、库存账实差异、周需求趋势；**全局筛选、KPI 下钻、SKU/运单/告警三级详情抽屉** |
| **AI 决策层** | 6 个可审计工具（库存 / 需求预测 / 补货计算 / 延期风险 what-if / 取货路径 / SOP 检索）+ **Function Calling 多轮 Agent**；防幻觉设计令数值计算 100% 走本地代码、调用过程可视化 |
| **决策闭环** | 全网补货建议单（3,000 SKU 巡检 **0.55s**，索引+批量优化）、**采纳/驳回审批留痕**、导出 CSV；SKU 详情含 52 周需求曲线、预测可靠性（MAPE）、批次效期、出入库流水 |

## 🏗 架构

```
① 数据源层：5 套异构系统模拟（ERP/WMS/TMS/MES/CRM）
      │ ETL（清洗 / 口径统一 / 派生：ABC-XYZ、周需求、告警）
② 数仓：SQLite warehouse.db（18 表 + 10 索引，已随仓库提交，可直接跑）
      │
③ API 服务（Python http.server, 8503）：大屏数据 + SKU/运单/告警详情 + AI 对话
      │
④ 前端（Vue3 + Vite + ECharts, 5174）：驾驶舱 / 下钻 / AI 对话 / 审批导出
```

## 📁 目录结构

```
├─ build_data.py        # 数据生成 + ETL（N_SKU=3000 可调；固定随机种子）
├─ api_server.py        # API 服务（8503，含 /api/ai/chat）
├─ agent.py             # DeepSeek Function Calling Agent（可切换私有化模型）
├─ export_excel.py      # 导出 Excel 数据包（可选）
├─ fused_tools/         # 6 个可审计工具（数据层，对接 warehouse.db）
├─ 知识库/               # SOP 文档（工具⑥ 知识库检索读取）
├─ data/warehouse.db   # 演示数仓（约 25MB，已随仓库提供）
└─ web-frontend/        # Vue3 + ECharts 大屏前端（npm install && npm run dev）
```

## 🚀 快速开始

```bash
# 1) Python 依赖（建议 venv）
pip install -r requirements.txt

# 2) 启动 API（8503）——data/warehouse.db 已随仓库提供，可直接跑
python api_server.py

# 3) 另开终端启动前端（5174）
cd web-frontend
npm install
npm run dev
# 浏览器打开 http://localhost:5174
```

可选：重建数仓 / 重出 Excel 数据包（会重新生成 data/warehouse.db 与 CSV）：
`python build_data.py`（先停 api_server）· `python export_excel.py`

- **AI 对话需要 API Key**：复制 `.env.example` 为 `.env` 并填入 `DEEPSEEK_API_KEY`；不填也可正常看大屏（AI 面板会提示）。
- **可选：重建数据 / 重出 Excel**：`python build_data.py`（先停 api_server，否则数据库被占用）、`python export_excel.py`。

## 🔌 API 概览（8503）

`/api/overview` · `/api/shipments` · `/api/alerts` · `/api/inventory` · `/api/inventory/summary` · `/api/orders/trend` · `/api/tracking/:id` · `/api/replenishment/proposal`（全网补货建议单）· `/api/forecast/accuracy`（预测可靠性）· `/api/skus` · `/api/sku/:sku`（详情：分仓/需求曲线/批次/流水）· `/api/shipment/:id`（含运费/关联订单/投诉）· `POST /api/ai/chat`、`/api/ai/reset`

## 📊 数据字典（摘要，18 表）

- 维度：products / customers / warehouses / vehicles / **suppliers**
- 事实：orders（52 周）、inventory（账实+安全库存）、shipments（含 delay/exception）、tracking（GPS）、production、complaints、alerts（ETL 派生，含处置建议与升级路径）
- 计划扩展：**fact_sku_plan**（ABC-XYZ/提前期/MOQ）、inbound（在途采购）、demand_weekly（52 周）、**stock_lot**（库位/批次/效期）、inout（出入库流水）、freight（运费结算）
- 派生口径：ABC 按年销售额累计占比（A≤75%/B≤95%）；周需求 = 订单按 SKU×周聚合；告警 = 延迟/账实差异/缺货/临期/破损丢件自动识别并分级闭环

## ⚡ 性能（本机实测）

单 SKU 查询 0.04s 级（与总量无关）｜全网补货巡检（3,000 SKU）0.55s｜预测可靠性全量 0.04s——单连接批量 + 缓存 + 索引实现，已做容量边界说明（README 同目录 `融合平台` 历史文档见 git log）。



## 🧰 技术栈

Python · SQLite · Vue3 · Vite · ECharts · DeepSeek API（Function Calling）· Node.js

## 🔗 参考

- [Microsoft — Inventory replenishment planning agent](https://adoption.microsoft.com/zh-CN/scenario-library/retail/inventory-replenishment-planning-agent/)
- [Agentic AI Framework for Smart Inventory Replenishment (arXiv)](https://arxiv.org/abs/2511.23366)
