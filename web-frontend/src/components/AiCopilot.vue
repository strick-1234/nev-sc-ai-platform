<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { api } from '../api';

const messages = ref([]);
const input = ref('');
const busy = ref(false);
const showModal = ref(false);      // 补货建议单
const showSkuList = ref(false);     // SKU 检索
const proposal = ref([]);
const selected = ref([]);
const decisions = ref({});
const skuList = ref([]);
const skuFilter = ref('');
const accuracyMap = ref({});

const filteredSku = computed(() => {
  const k = skuFilter.value.trim().toLowerCase();
  if (!k) return skuList.value;
  return skuList.value.filter((s) =>
    (s.sku + ' ' + s.name + ' ' + (s.category || '')).toLowerCase().includes(k));
});

function openSku(s) {
  window.dispatchEvent(new CustomEvent('open-sku', { detail: { sku: s.sku } }));
  showSkuList.value = false;
  showModal.value = false;
}

async function send() {
  const text = input.value.trim();
  if (!text || busy.value) return;
  input.value = '';
  messages.value.push({ role: 'user', content: text });
  busy.value = true;
  try {
    const r = await api.chat(text);
    messages.value.push({ role: 'assistant', content: r.answer, trace: r.trace || [] });
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '调用失败：' + e.message, trace: [] });
  } finally {
    busy.value = false;
  }
}

async function reset() {
  try { await api.reset(); } catch (e) { /* ignore */ }
  messages.value = [];
}

async function openProposal() {
  showModal.value = true;
  proposal.value = [];
  try {
    proposal.value = await api.replenishmentProposal();
  } catch (e) {
    proposal.value = [{ sku: '加载失败', name: e.message, available: '', rop: '', suggested_order_qty: '' }];
  }
}

async function openSkuList() {
  showSkuList.value = true;
  skuFilter.value = '';
  if (!skuList.value.length) {
    try { skuList.value = await api.skuList(); } catch (e) { skuList.value = []; }
  }
  if (!Object.keys(accuracyMap.value).length) {
    try {
      const acc = await api.forecastAccuracy();
      acc.forEach((a) => { accuracyMap.value[a.sku] = a; });
    } catch (e) { /* ignore */ }
  }
}

function relClass(sku) {
  const a = accuracyMap.value[sku];
  return a ? 'rel-' + a.reliability : '';
}

function toggle(sku) {
  const i = selected.value.indexOf(sku);
  if (i >= 0) selected.value.splice(i, 1);
  else selected.value.push(sku);
}

function decide(sku, st) {
  decisions.value[sku] = st;
}

function exportCsv() {
  const rows = proposal.value.filter((p) => !p.sku || selected.value.length === 0 || selected.value.includes(p.sku));
  const head = ['SKU', '名称', 'ABC', '可用', 'ROP', '建议补货', '断料周', '提前期(周)', 'MOQ', '审批状态'];
  const lines = [head.join(',')];
  for (const p of rows) {
    lines.push([
      p.sku, '"' + (p.name || '') + '"', p.abc_class, p.available, p.rop,
      p.suggested_order_qty, p.stockout_week || '', p.lead_time_weeks, p.moq,
      decisions.value[p.sku] || '待处理',
    ].join(','));
  }
  const csv = '\ufeff' + lines.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '补货建议单.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}

function onAskAi(e) {
  const text = (e.detail && e.detail.text) || '';
  if (text) input.value = text;
}

onMounted(() => window.addEventListener('ask-ai', onAskAi));
onBeforeUnmount(() => window.removeEventListener('ask-ai', onAskAi));
</script>

<template>
  <aside class="ai-side">
    <div class="ai-head">
      <div>
        <div class="ai-title">🤖 AI 计划员</div>
        <div class="ai-sub">对话式供应链决策</div>
      </div>
      <div class="head-btns">
        <button class="ai-reset" @click="openSkuList">🔍 SKU</button>
        <button class="ai-reset" @click="openProposal">📋 建议单</button>
        <button class="ai-reset" @click="reset">重置</button>
      </div>
    </div>

    <div class="ai-msgs">
      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <div class="txt">{{ m.content }}</div>
        <details v-if="m.trace && m.trace.length" class="trace">
          <summary>工具调用 {{ m.trace.length }} 步</summary>
          <div v-for="(t, j) in m.trace" :key="j" class="trace-item">
            <b>{{ t.tool }}</b> {{ JSON.stringify(t.args) }}
            <div class="trace-head">{{ t.head }}</div>
          </div>
        </details>
      </div>
      <div v-if="busy" class="msg assistant">思考中…</div>
    </div>

    <div class="ai-input">
      <input v-model="input" @keyup.enter="send" placeholder="问：SKU0001 库存 / 补货 / 延期风险…" />
      <button @click="send" :disabled="busy">发送</button>
    </div>

    <!-- 补货建议单 -->
    <div v-if="showModal" class="overlay" @click.self="showModal = false">
      <div class="modal">
        <div class="modal-head">
          <b>📋 全网补货建议单</b>
          <button class="ai-reset" @click="showModal = false">关闭</button>
        </div>
        <div class="modal-tip">点击 SKU/名称看详情；可勾选导出 CSV；支持逐条「采纳/驳回」留痕。演示：真实系统此处将回写 ERP 采购单并进入审批。</div>
        <div class="modal-body">
          <table>
            <thead><tr>
              <th>选</th><th>SKU</th><th>名称</th><th>ABC</th><th>可用</th><th>ROP</th><th>建议补货</th><th>断料周</th><th>决策</th>
            </tr></thead>
            <tbody>
              <tr v-for="p in proposal" :key="p.sku">
                <td><input type="checkbox" :checked="selected.includes(p.sku)" @change="toggle(p.sku)" /></td>
                <td class="link" @click="openSku(p)">{{ p.sku }}</td>
                <td class="link" @click="openSku(p)">{{ p.name }}</td>
                <td>{{ p.abc_class }}</td><td>{{ p.available }}</td><td>{{ p.rop }}</td>
                <td class="qty">{{ p.suggested_order_qty }}</td><td>{{ p.stockout_week || '-' }}</td>
                <td class="dec">
                  <span v-if="decisions[p.sku]==='采纳'" class="ok">已采纳</span>
                  <span v-else-if="decisions[p.sku]==='驳回'" class="no">已驳回</span>
                  <span v-else class="dim">待处理</span>
                  <div class="dec-btns">
                    <button class="mini" @click.stop="decide(p.sku,'采纳')">采纳</button>
                    <button class="mini" @click.stop="decide(p.sku,'驳回')">驳回</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!proposal.length" class="modal-tip">加载中…</div>
        </div>
        <div class="modal-foot">
          <button class="ai-reset" @click="exportCsv">⬇️ 导出选中/全部 CSV</button>
        </div>
      </div>
    </div>

    <!-- SKU 检索 -->
    <div v-if="showSkuList" class="overlay" @click.self="showSkuList = false">
      <div class="modal">
        <div class="modal-head">
          <b>🔍 SKU 检索（全部 {{ skuList.length }} 个）</b>
          <button class="ai-reset" @click="showSkuList = false">关闭</button>
        </div>
        <div class="modal-tip">
          <input class="search" v-model="skuFilter" placeholder="输入 SKU / 名称 / 类别 过滤…" />
        </div>
        <div class="modal-body">
          <table>
            <thead><tr><th>SKU</th><th>名称</th><th>类别</th><th>ABC</th><th>XYZ</th><th>MAPE</th><th>可靠性</th></tr></thead>
            <tbody>
              <tr v-for="s in filteredSku" :key="s.sku" class="row" @click="openSku(s)">
                <td class="link">{{ s.sku }}</td><td class="link">{{ s.name }}</td>
                <td>{{ s.category }}</td><td>{{ s.abc_class }}</td><td>{{ s.xyz_class }}</td>
                <td>{{ accuracyMap[s.sku] && accuracyMap[s.sku].mape != null ? (accuracyMap[s.sku].mape * 100).toFixed(1) + '%' : '-' }}</td>
                <td><span :class="relClass(s.sku)">{{ accuracyMap[s.sku] ? accuracyMap[s.sku].reliability : '…' }}</span></td>
              </tr>
            </tbody>
          </table>
          <div v-if="!filteredSku.length" class="modal-tip">无匹配 SKU</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.ai-side{width:360px;min-width:360px;height:100vh;display:flex;flex-direction:column;
  background:linear-gradient(180deg,#0b1e3a,#060d1f);border-left:1px solid rgba(56,189,248,.25);}
.ai-head{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid rgba(56,189,248,.2);}
.ai-title{font-size:17px;font-weight:700;color:#e0f2fe;}
.ai-sub{font-size:12px;color:#93c5fd;}
.head-btns{display:flex;gap:6px;}
.ai-reset{background:rgba(56,189,248,.15);color:#7dd3fc;border:1px solid rgba(56,189,248,.35);border-radius:6px;padding:4px 8px;cursor:pointer;font-size:12px;}
.ai-msgs{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;}
.msg{border-radius:8px;padding:8px 10px;font-size:13px;line-height:1.6;max-width:94%;}
.msg .txt{white-space:pre-wrap;word-break:break-word;}
.msg.user{align-self:flex-end;background:rgba(56,189,248,.2);color:#e0f2fe;}
.msg.assistant{align-self:flex-start;background:rgba(255,255,255,.05);color:#dbeafe;}
.trace{margin-top:6px;font-size:11px;color:#7dd3fc;}
.trace-item{margin-top:4px;padding:4px 6px;background:rgba(0,0,0,.25);border-radius:5px;}
.trace-head{color:#93c5fd;margin-top:2px;white-space:pre-wrap;word-break:break-all;}
.ai-input{display:flex;gap:8px;padding:12px;border-top:1px solid rgba(56,189,248,.2);}
.ai-input input{flex:1;background:#060d1f;border:1px solid rgba(56,189,248,.3);border-radius:8px;color:#dbeafe;padding:8px 10px;font-size:13px;}
.ai-input button{background:#0ea5e9;color:#fff;border:none;border-radius:8px;padding:0 14px;cursor:pointer;font-size:13px;}
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;z-index:55;}
.modal{width:720px;max-width:92vw;max-height:82vh;display:flex;flex-direction:column;background:#0b1e3a;border:1px solid rgba(56,189,248,.4);border-radius:12px;}
.modal-head{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;color:#e0f2fe;}
.modal-tip{padding:0 16px 10px;font-size:12px;color:#93c5fd;}
.search{width:100%;background:#060d1f;border:1px solid rgba(56,189,248,.3);border-radius:6px;color:#dbeafe;padding:7px 10px;font-size:13px;}
.modal-body{flex:1;overflow:auto;padding:0 16px;}
table{width:100%;border-collapse:collapse;font-size:12px;color:#dbeafe;}
th,td{padding:7px 8px;border-bottom:1px solid rgba(56,189,248,.15);text-align:left;}
th{color:#7dd3fc;position:sticky;top:0;background:#0b1e3a;}
td.qty{color:#fbbf24;font-weight:700;}
td.link{color:#7dd3fc;cursor:pointer;text-decoration:underline;}
.dec .ok{color:#4ade80;font-size:11px;}
.dec .no{color:#f87171;font-size:11px;}
.dec .dim{color:#8b9db8;font-size:11px;}
.dec-btns{display:flex;gap:4px;margin-top:3px;}
.mini{background:rgba(56,189,248,.15);color:#7dd3fc;border:1px solid rgba(56,189,248,.35);border-radius:4px;padding:1px 6px;font-size:11px;cursor:pointer;}
.rel-可靠{color:#4ade80;}
.rel-一般{color:#fbbf24;}
.rel-不可靠{color:#f87171;}
.rel-样本不足{color:#8b9db8;}
tr.row{cursor:pointer;}
tr.row:hover{background:rgba(56,189,248,.08);}
.modal-foot{padding:12px 16px;text-align:right;}
</style>
