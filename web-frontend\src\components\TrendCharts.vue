<template>
  <div class="panel">
    <div class="panel-title">运单状态分布 / 周需求趋势</div>
    <div class="panel-body" style="display:flex; gap:12px;">
      <div ref="pieRef" style="flex:1; min-height:260px;"></div>
      <div ref="lineRef" style="flex:1; min-height:260px;"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
  shipStatus: { type: Array, default: () => [] },
  ordersTrend: { type: Array, default: () => [] },
});

const pieRef = ref(null);
const lineRef = ref(null);
let pie = null;
let line = null;

const statusColor = { '在途': '#38bdf8', '已签收': '#4ade80', '待发运': '#94a3b8', '异常': '#f87171' };

function renderPie() {
  if (!pie) return;
  pie.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#bae6fd' } },
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '45%'],
      label: { color: '#dbeafe', formatter: '{b}: {c}' },
      data: props.shipStatus.map((s) => ({ name: s.status, value: s.c, itemStyle: { color: statusColor[s.status] || '#94a3b8' } })),
    }],
  });
}

function renderLine() {
  if (!line) return;
  line.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 45, right: 15, top: 20, bottom: 35 },
    xAxis: { type: 'category', data: props.ordersTrend.map((o) => o.order_date), axisLabel: { color: '#9db8d8', rotate: 30, fontSize: 10, interval: 7 } },
    yAxis: { type: 'value', axisLabel: { color: '#9db8d8' }, splitLine: { lineStyle: { color: 'rgba(59,130,246,0.15)' } } },
    series: [{
      name: '周需求(件)', type: 'line', smooth: true,
      data: props.ordersTrend.map((o) => o.c),
      itemStyle: { color: '#38bdf8' },
      areaStyle: { color: 'rgba(56,189,248,0.15)' },
    }],
  });
}

const onResize = () => { pie && pie.resize(); line && line.resize(); };

onMounted(() => {
  pie = echarts.init(pieRef.value);
  line = echarts.init(lineRef.value);
  renderPie();
  renderLine();
  window.addEventListener('resize', onResize);
});
watch(() => [props.shipStatus, props.ordersTrend], () => { renderPie(); renderLine(); }, { deep: true });
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  pie && pie.dispose();
  line && line.dispose();
});
</script>
