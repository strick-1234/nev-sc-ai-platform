<template>
  <div class="panel">
    <div class="panel-title">在途运输可视化（全国轨迹地图）</div>
    <div class="panel-body">
      <div ref="mapRef" class="map"></div>
      <div class="map-tools">
        <select v-model="selectedId" @change="loadTrack">
          <option value="">-- 选择运单查看轨迹回放 --</option>
          <option v-for="s in activeShipments" :key="s.shipment_id" :value="s.shipment_id">
            {{ s.shipment_id }} · {{ s.origin }}→{{ s.dest }}
          </option>
        </select>
      </div>
      <div v-if="selectedInfo" class="map-info">
        <div><b>{{ selectedInfo.shipment_id }}</b> {{ selectedInfo.origin }}→{{ selectedInfo.dest }}</div>
        <div>{{ selectedInfo.carrier }} · {{ selectedInfo.status }} · 延迟 {{ selectedInfo.delay_min }} 分钟</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue';
import * as echarts from 'echarts';
import { api } from '../api';
import chinaGeo from '../assets/china.json';

// 城市坐标（用于画运输线路）
const CITY_COORDS = {
  '北京': [116.41, 39.90], '上海': [121.47, 31.23], '广州': [113.26, 23.13],
  '深圳': [114.06, 22.55], '杭州': [120.15, 30.28], '成都': [104.07, 30.57],
  '武汉': [114.30, 30.59], '西安': [108.94, 34.34], '重庆': [106.55, 29.56],
  '南京': [118.80, 32.06], '苏州': [120.62, 31.32], '天津': [117.20, 39.08],
  '青岛': [120.38, 36.07], '郑州': [113.62, 34.75], '长沙': [112.94, 28.23],
  '昆明': [102.83, 24.88], '沈阳': [123.43, 41.80], '厦门': [118.09, 24.48],
  '哈尔滨': [126.53, 45.80], '乌鲁木齐': [87.62, 43.82], '贵阳': [106.63, 26.65],
  '南宁': [108.32, 22.82],
};

const props = defineProps({ shipments: { type: Array, default: () => [] } });
const mapRef = ref(null);
const selectedId = ref('');
const selectedInfo = ref(null);
let chart = null;

const activeShipments = computed(() =>
  props.shipments.filter((s) => s.status === '在途' || s.status === '异常')
);

function baseOption() {
  const transit = [];
  const exception = [];
  const routes = [];
  for (const s of props.shipments) {
    if (s.status === '在途') transit.push({ name: s.shipment_id, value: [s.lng, s.lat] });
    else if (s.status === '异常') exception.push({ name: s.shipment_id, value: [s.lng, s.lat] });
    const o = CITY_COORDS[s.origin];
    const d = CITY_COORDS[s.dest];
    if (o && d && (s.status === '在途' || s.status === '异常')) routes.push({ coords: [o, d] });
  }
  return {
    tooltip: { trigger: 'item', formatter: (p) => p.name || '' },
    geo: {
      map: 'china',
      roam: true,
      itemStyle: { areaColor: '#0b2a4a', borderColor: '#2b6cb0', borderWidth: 0.6 },
      emphasis: { itemStyle: { areaColor: '#164e7a' }, label: { show: false } },
      label: { show: false },
    },
    series: [
      { id: 'routes', name: '运输线路', type: 'lines', coordinateSystem: 'geo', zlevel: 1,
        data: routes, lineStyle: { color: '#38bdf8', width: 1, opacity: 0.35, curveness: 0.2 },
        effect: { show: true, period: 5, trailLength: 0.2, symbolSize: 3 } },
      { id: 'transit', name: '在途', type: 'effectScatter', coordinateSystem: 'geo', zlevel: 2,
        data: transit, symbolSize: 7, rippleEffect: { brushType: 'stroke' }, itemStyle: { color: '#38bdf8' } },
      { id: 'exception', name: '异常', type: 'effectScatter', coordinateSystem: 'geo', zlevel: 2,
        data: exception, symbolSize: 10, rippleEffect: { brushType: 'stroke' }, itemStyle: { color: '#f87171' } },
      { id: 'track', name: '轨迹回放', type: 'lines', coordinateSystem: 'geo', zlevel: 3,
        data: [], lineStyle: { color: '#fbbf24', width: 2.5, curveness: 0.15 },
        effect: { show: true, period: 3, trailLength: 0.4, symbol: 'arrow', symbolSize: 6 } },
    ],
  };
}

function render() {
  if (chart) chart.setOption(baseOption(), true);
}

async function loadTrack() {
  if (!selectedId.value) {
    selectedInfo.value = null;
    if (chart) chart.setOption({ series: [{ id: 'track', data: [] }] });
    return;
  }
  const s = props.shipments.find((x) => x.shipment_id === selectedId.value);
  selectedInfo.value = s || null;
  const pts = await api.tracking(selectedId.value);
  const coords = pts.map((p) => [p.lng, p.lat]);
  if (chart) chart.setOption({ series: [{ id: 'track', data: [{ coords }] }] });
}

const onResize = () => chart && chart.resize();

onMounted(() => {
  echarts.registerMap('china', chinaGeo);
  chart = echarts.init(mapRef.value);
  render();
  chart.on('click', (p) => {
    if (p.seriesType === 'effectScatter' && p.name) {
      window.dispatchEvent(new CustomEvent('open-shipment', { detail: { id: p.name } }));
    }
  });
  window.addEventListener('resize', onResize);
});

watch(() => props.shipments, () => { render(); if (selectedId.value) loadTrack(); }, { deep: true });

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  chart && chart.dispose();
});
</script>
