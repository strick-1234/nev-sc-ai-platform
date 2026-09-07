<script setup>
import { ref, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { api } from '../api';

const props = defineProps({ sku: String });
const emit = defineEmits(['close']);
const detail = ref(null);
const chartEl = ref(null);
let chart = null;

watch(() => props.sku, async (sku) => {
  if (!sku) { detail.value = null; return; }
  detail.value = null;
  try {
    detail.value = await api.skuDetail(sku);
    await nextTick();
    renderChart();
  } catch (e) {
    detail.value = { name: '加载失败', error: e.message };
  }
});

function renderChart() {
  if (!detail.value || !chartEl.value) return;
  try {
    if (chart) chart.dispose();
    chart = echarts.init(chartEl.value);
    const hist = (detail.value.weekly || []).map((w) => [w.week, w.demand]);
    const fc = (detail.value.forecast || []).map((f) => [f.week, f.demand]);
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['历史需求', '预测'], textStyle: { color: '#bae6fd' } },
      grid: { left: 48, right: 16, top: 34, bottom: 34 },
      xAxis: { type: 'value', name: '周', min: 1, axisLabel: { color: '#9db8d8' }, nameTextStyle: { color: '#9db8d8' } },
      yAxis: { type: 'value', name: '需求', axisLabel: { color: '#9db8d8' }, nameTextStyle: { color: '#9db8d8' }, splitLine: { lineStyle: { color: 'rgba(59,130,246,.15)' } } },
      series: [
        { name: '历史需求', type: 'line', data: hist, symbol: 'none', lineStyle: { color: '#38bdf8' }, areaStyle: { color: 'rgba(56,189,248,.12)' } },
        { name: '预测', type: 'line', data: fc, symbol: 'circle', symbolSize: 6, lineStyle: { color: '#fbbf24', type: 'dashed' } },
      ],
    });
  } catch (e) {
    console.error('SKU 图表渲染失败:', e);
  }
}
</script>

<template>
  <div v-if="sku" class="overlay" @click.self="emit('close')">
    <aside class="drawer">
      <div class="d-head">
        <div>
          <div class="d-title">{{ detail ? detail.sku : '' }} {{ detail ? detail.name : '' }}</div>
          <div class="d-sub">{{ detail && detail.category }} · {{ detail && detail.abc_class }}{{ detail && detail.xyz_class }} 类 · 单价 {{ detail && detail.unit_price }} 元</div>
        </div>
        <button class="x" @click="emit('close')">✕</button>
      </div>

      <div v-if="detail && detail.error" class="d-body"><p>{{ detail.error }}</p></div>
      <div v-else-if="detail" class="d-body">
        <div class="kv-grid">
          <div><b>供应商</b>{{ detail.supplier }}</div>
          <div><b>准时率</b>{{ (detail.on_time_rate * 100).toFixed(1) }}%</div>
          <div><b>提前期</b>{{ detail.lead_time_weeks }} 周</div>
          <div><b>MOQ</b>{{ detail.moq }}</div>
        </div>

        <div class="acc" v-if="detail.accuracy">
          近 8 周朴素基线 MAPE
          <b>{{ detail.accuracy.mape != null ? (detail.accuracy.mape * 100).toFixed(1) + '%' : '-' }}</b>
          · 周波动系数 CV
          <b>{{ detail.accuracy.cv != null ? (detail.accuracy.cv * 100).toFixed(1) + '%' : '-' }}</b>
          <span class="dim">（误差越小预测越可靠；Z 类间歇件通常偏高）</span>
        </div>

        <div class="rep" v-if="detail.replenish">
          <div class="rep-item"><span>可用</span><b>{{ detail.replenish.available }}</b></div>
          <div class="rep-item"><span>ROP</span><b>{{ detail.replenish.rop }}</b></div>
          <div class="rep-item"><span>安全库存</span><b>{{ detail.replenish.safety_stock }}</b></div>
          <div class="rep-item"><span>建议补货</span><b class="qty">{{ detail.replenish.suggested_order_qty }}</b></div>
          <div class="rep-item"><span>断料周(不下单)</span><b class="bad">{{ detail.replenish.stockout_week || '-' }}</b></div>
        </div>

        <div class="chart" ref="chartEl"></div>

        <div class="sec-title">分仓库存</div>
        <table>
          <thead><tr><th>仓库</th><th>实际</th><th>账面</th><th>安全库存</th></tr></thead>
          <tbody>
            <tr v-for="r in detail.inventory" :key="r.wh_code">
              <td>{{ r.wh_name }}</td><td>{{ r.actual_qty }}</td><td>{{ r.book_qty }}</td><td>{{ r.safety_stock }}</td>
            </tr>
          </tbody>
        </table>

        <div class="sec-title">在途采购</div>
        <div v-if="detail.inbound.length">
          <div v-for="b in detail.inbound" :key="b.po_id" class="ib">{{ b.qty }} 件 · 约 {{ b.eta_week }} 周后到</div>
        </div>
        <div v-else class="dim">无在途采购</div>

        <div class="sec-title">库存批次明细（库位 / 效期）</div>
        <table>
          <thead><tr><th>库位</th><th>批次</th><th>数量</th><th>效期</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="l in detail.lots" :key="l.batch_no">
              <td>{{ l.location }}</td><td>{{ l.batch_no }}</td><td>{{ l.lot_qty }}</td>
              <td>{{ l.expiry_date || '—' }}</td><td>{{ l.status }}</td>
            </tr>
          </tbody>
        </table>

        <div class="sec-title">近期出入库流水</div>
        <table>
          <thead><tr><th>仓库</th><th>类型</th><th>数量</th><th>单据</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(m, i) in detail.inout" :key="i">
              <td>{{ m.wh_code }}</td><td>{{ m.io_type }}</td><td>{{ m.qty }}</td><td>{{ m.ref_no }}</td><td>{{ m.ts }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;display:flex;justify-content:flex-end;}
.drawer{width:480px;max-width:94vw;height:100vh;background:#0b1e3a;border-left:1px solid rgba(56,189,248,.35);display:flex;flex-direction:column;}
.d-head{display:flex;justify-content:space-between;align-items:center;padding:16px;border-bottom:1px solid rgba(56,189,248,.25);}
.d-title{font-size:18px;font-weight:700;color:#e0f2fe;}
.d-sub{font-size:12px;color:#93c5fd;margin-top:3px;}
.x{background:none;border:none;color:#9ec8f5;font-size:18px;cursor:pointer;}
.d-body{flex:1;overflow:auto;padding:14px 16px;}
.kv-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;color:#dbeafe;}
.kv-grid b{color:#7dd3fc;margin-right:4px;}
.rep{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0;}
.acc{font-size:12px;color:#9db8d8;margin:8px 0 2px;padding:8px 10px;background:rgba(255,255,255,.03);border:1px solid #2a3a55;border-radius:8px;}
.acc b{color:#e0f2fe;}
.acc .dim{color:#8b9db8;}
.rep-item{flex:1;min-width:80px;background:rgba(255,255,255,.04);border:1px solid #2a3a55;border-radius:8px;padding:8px;text-align:center;}
.rep-item span{display:block;font-size:11px;color:#8b9db8;}
.rep-item b{font-size:16px;color:#e0f2fe;}
.rep-item .qty{color:#fbbf24;}
.rep-item .bad{color:#f87171;}
.chart{height:180px;margin:8px 0;}
.sec-title{font-size:13px;color:#7dd3fc;margin:12px 0 6px;}
table{width:100%;border-collapse:collapse;font-size:12px;color:#dbeafe;}
th,td{padding:6px 8px;border-bottom:1px solid rgba(56,189,248,.15);text-align:left;}
th{color:#7dd3fc;}
.ib{font-size:13px;color:#dbeafe;margin:4px 0;}
.dim{font-size:12px;color:#8b9db8;}
</style>
