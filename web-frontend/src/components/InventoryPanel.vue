<template>
  <div class="panel">
    <div class="panel-title">库存准确率看板（多仓统一视图）</div>
    <div class="panel-body" style="display:flex; gap:12px;">
      <div ref="chartRef" style="flex:1; min-height:260px;"></div>
      <div style="width:230px; display:flex; flex-direction:column;">
        <div style="text-align:center; padding:8px; border:1px solid rgba(251,191,36,0.3); border-radius:8px;">
          <div style="font-size:28px; font-weight:700; color:#fbbf24;">{{ pct }}</div>
          <div style="font-size:12px; color:#9ec8f5;">库存准确率</div>
          <div style="font-size:12px; color:#f87171; margin-top:6px;">缺货 {{ lowStock }} 项</div>
        </div>
        <div style="margin-top:10px; flex:1;">
          <div style="font-size:13px; color:#bae6fd; margin-bottom:8px;">账实差异 TOP5</div>
          <div v-for="r in topDiff" :key="r.id" style="font-size:12px; color:#9db8d8; margin-bottom:5px; display:flex; justify-content:space-between; align-items:center;">
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; cursor:pointer;" title="查看 SKU 详情" @click="openSku(r)">{{ r.product_name }}</span>
            <span style="display:flex; gap:6px; align-items:center;">
              <b style="color:#fbbf24;">{{ r.diff_qty }}</b>
              <button class="ask-ai" @click="openSku(r)" title="查看详情">🔍</button>
              <button class="ask-ai" @click="askAI(r)" title="问 AI">🤖</button>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
  inventory: { type: Array, default: () => [] },
  summary: { type: Array, default: () => [] },
  accuracy: { type: Number, default: 1 },
  lowStock: { type: Number, default: 0 },
});

const chartRef = ref(null);
let chart = null;

const pct = computed(() => (props.accuracy * 100).toFixed(2) + '%');
const topDiff = computed(() =>
  [...props.inventory].sort((a, b) => Math.abs(b.diff_qty) - Math.abs(a.diff_qty)).slice(0, 5)
);

function render() {
  if (!chart) return;
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['账面库存', '实际库存'], textStyle: { color: '#bae6fd' } },
    grid: { left: 50, right: 15, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: props.summary.map((r) => r.wh_name),
      axisLabel: { color: '#9db8d8', rotate: 30, fontSize: 10 },
    },
    yAxis: { type: 'value', axisLabel: { color: '#9db8d8' }, splitLine: { lineStyle: { color: 'rgba(59,130,246,0.15)' } } },
    series: [
      { name: '账面库存', type: 'bar', data: props.summary.map((r) => r.book), itemStyle: { color: '#38bdf8' } },
      { name: '实际库存', type: 'bar', data: props.summary.map((r) => r.actual), itemStyle: { color: '#4ade80' } },
    ],
  });
}

const onResize = () => chart && chart.resize();

function askAI(r) {
  window.dispatchEvent(new CustomEvent('ask-ai', {
    detail: { text: `SKU ${r.sku}（${r.product_name}）账实差异 ${r.diff_qty}，需要处理吗？` },
  }));
}

function openSku(r) {
  window.dispatchEvent(new CustomEvent('open-sku', { detail: { sku: r.sku } }));
}

onMounted(() => {
  chart = echarts.init(chartRef.value);
  render();
  window.addEventListener('resize', onResize);
});
watch(() => props.summary, render, { deep: true });
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  chart && chart.dispose();
});
</script>

<style scoped>
.ask-ai { background: rgba(56,189,248,.12); color: #7dd3fc; border: 1px solid rgba(56,189,248,.35);
  border-radius: 5px; padding: 1px 6px; font-size: 11px; cursor: pointer; }
</style>
