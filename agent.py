# -*- coding: utf-8 -*-
"""融合平台 · Agent 编排（DeepSeek Function Calling）。

与根目录 AI 计划员同一套架构：本地可审计工具 + LLM 编排；
数据源为融合数仓 warehouse.db。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent


def _load_env() -> None:
    env_file = HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v


def deepseek_config() -> dict:
    _load_env()
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key or key.startswith("sk-你的"):
        raise RuntimeError("未找到 DeepSeek API key：请在 融合平台\\.env 中配置 DEEPSEEK_API_KEY")
    return {
        "api_key": key,
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip(),
    }


from fused_tools import (  # noqa: E402
    inventory_tool,
    knowledge_tool,
    replenish_tool,
    risk_tool,
    route_tool,
)
from fused_tools.forecast_tool import forecast_demand  # noqa: E402

SYSTEM_PROMPT = """你是新能源汽车售后零部件供应链的智能计划助手「AI 计划员」，服务对象是负责需求计划与库存管理的计划员。

【你能做的事】查询产品全网库存（分仓+在途）、预测未来需求、计算补货建议、模拟供应商延期的缺料风险、优化取货路径、检索 SOP 知识库。

【必须遵守的规则】
1. 所有数据一律以工具返回为准，禁止自行估算或编造数字；
2. 工具返回的 text 字段是整理好的中文结论，可直接引用并补充解释；
3. 回答用简体中文，先结论后依据，关键数字必须出现；
4. 产品用 SKU（如 SKU0001）或中文名（动力电芯）查询，工具支持模糊搜索；
5. 超出能力范围的问题如实说明；"要不要补货/补多少/会不会断料"必须调用补货/风险工具，不能凭直觉回答。

【当前可调用工具】① 库存查询 ② 需求预测 ③ 补货计算 ④ 缺料风险模拟 ⑤ 路径优化 ⑥ SOP 知识库检索。"""

MAX_ROUNDS = 10

TOOLS = [
    {"type": "function", "function": {"name": "query_inventory",
     "description": "查询产品全网库存：分仓实际库存、在途采购、供应商、提前期、可用覆盖周数。支持 SKU（SKU0001）或中文名（动力电芯）模糊搜索。",
     "parameters": {"type": "object", "properties": {"sku": {"type": "string", "description": "SKU 或名称，如 SKU0001 / 动力电芯"}}, "required": ["sku"]}}},
    {"type": "function", "function": {"name": "forecast_demand",
     "description": "预测某 SKU 未来 N 周需求（52 周销售历史，含季节性与波动σ）。",
     "parameters": {"type": "object", "properties": {"sku": {"type": "string", "description": "SKU，如 SKU0001"}, "weeks": {"type": "integer", "description": "预测周数，默认4，范围1-8"}}, "required": ["sku"]}}},
    {"type": "function", "function": {"name": "calc_replenishment",
     "description": "计算补货决策：ABC 分层服务水平 → 安全库存/ROP/目标库存，对比全网可用（实际+在途）给出建议补货量与断料预警。",
     "parameters": {"type": "object", "properties": {"sku": {"type": "string", "description": "SKU，如 SKU0001"}, "service_level": {"type": "number", "description": "可选 0-1，如 0.95；不传按 ABC 默认"}}, "required": ["sku"]}}},
    {"type": "function", "function": {"name": "simulate_stockout",
     "description": "缺料风险模拟(what-if)：假设供应商延期若干周或本周不下单，逐周推演是否会断料、断在哪周、最大缺口多少。",
     "parameters": {"type": "object", "properties": {"sku": {"type": "string", "description": "SKU，如 SKU0001"}, "delay_weeks": {"type": "integer", "description": "供应商延期周数，默认0"}, "assume_order": {"type": "boolean", "description": "是否假设按建议补货量下单，默认true"}}, "required": ["sku"]}}},
    {"type": "function", "function": {"name": "optimize_route",
     "description": "取货路径优化：从华东备件中心仓(上海)出发遍历指定供应商取货后返回，输出最优顺序与分段里程。",
     "parameters": {"type": "object", "properties": {"supplier_ids": {"type": "string", "description": "逗号分隔供应商编号或城市名，如 'S-01,S-02,S-04,S-05' 或 '苏州,常州'"}}, "required": ["supplier_ids"]}}},
    {"type": "function", "function": {"name": "search_knowledge",
     "description": "SOP 知识库检索（供应商交付管理、缺料升级流程）。",
     "parameters": {"type": "object", "properties": {"question": {"type": "string", "description": "检索问题，如 '准时率考核标准'"}}, "required": ["question"]}}},
]

FUNC_MAP = {
    "query_inventory": inventory_tool.query_inventory,
    "forecast_demand": forecast_demand,
    "calc_replenishment": replenish_tool.calc_replenishment,
    "simulate_stockout": risk_tool.simulate_stockout,
    "optimize_route": route_tool.optimize_route,
    "search_knowledge": knowledge_tool.search_knowledge,
}


def _dump(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, default=str)


class AgentSession:
    def __init__(self) -> None:
        cfg = deepseek_config()
        self.client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
        self.model = cfg["model"]
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.trace: list[dict] = []

    def ask(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        for _ in range(MAX_ROUNDS):
            resp = self.client.chat.completions.create(
                model=self.model, messages=self.messages, tools=TOOLS, temperature=0.2)
            msg = resp.choices[0].message
            if not msg.tool_calls:
                answer = msg.content or "(模型未返回内容)"
                self.messages.append({"role": "assistant", "content": answer})
                return answer
            self.messages.append({
                "role": "assistant", "content": msg.content,
                "tool_calls": [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                               for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                name, raw = tc.function.name, tc.function.arguments or "{}"
                try:
                    args = json.loads(raw)
                except json.JSONDecodeError:
                    args = {}
                step = {"tool": name, "args": args}
                try:
                    result = FUNC_MAP[name](**args) if name in FUNC_MAP else {"ok": False, "text": f"未知工具 {name}"}
                    if not isinstance(result, dict):
                        result = {"ok": True, "text": str(result)}
                except Exception as exc:  # noqa: BLE001
                    result = {"ok": False, "text": f"工具执行出错：{exc}"}
                step["result_head"] = result.get("text", _dump(result))[:400]
                self.trace.append(step)
                self.messages.append({"role": "tool", "tool_call_id": tc.id, "content": _dump(result)})
        return "对话轮次超限，请换一种问法或拆分问题。"
