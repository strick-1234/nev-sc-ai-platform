<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { api } from './api';
import KpiCard from './components/KpiCard.vue';
import TransitMap from './components/TransitMap.vue';
import AlertsPanel from './components/AlertsPanel.vue';
import InventoryPanel from './components/InventoryPanel.vue';
import DataSourcePanel from './components/DataSourcePanel.vue';
import TrendCharts from './components/TrendCharts.vue';
import AiCopilot from './components/AiCopilot.vue';
import SkuDrawer from './components/SkuDrawer.vue';
import ShipmentDrawer from './components/ShipmentDrawer.vue';
import DetailModal from './components/DetailModal.vue';
import AlertDrawer from './components/AlertDrawer.vue';

const overview = ref(null);
const shipments = ref([]);
const alerts = ref([]);
const inventory = ref([]);
const invSummary = ref([]);
const datasources = ref([]);
const shipStatus = ref([]);
const ordersTrend = ref([]);
const skuId = ref(null);
const shipId = ref(null);
const alertDetail = ref(null);

const loading = ref(false);
const loadError = ref('');
const lastUpdated = ref('');

// 全局筛选
const whFilter = ref('');
const catFilter = ref('');
const alertLevel = ref('');
const shipStatusFilter = ref('');

// KPI 下钻明细弹窗
const detailModal = ref(null);

const categories = computed(() => [...new Set(inventory.value.map((r) => r.category).filter(Boolean))]);
const whOptions = computed(() => invSummary.value.map((r) => ({ wh_code: r.wh_code, wh_name: r.wh_name })));

const filteredShipments = computed(() =>
  shipStatusFilter.value ? shipments.value.filter((s) => s.status === shipStatusFilter.value) : shipments.value);
const filteredAlerts = computed(() =>
  alertLevel.value ? alerts.value.filter((a) => a.level === alertLevel.value) : alerts.value);
const filteredInventory = computed(() => inventory.value.filter((r) =>
  (!whFilter.value || r.wh_code === whFilter.value) && (!catFilter.value || r.category === catFilter.value)));
const filteredSummary = computed(() =>
  whFilter.value ? invSummary.value.filter((r) => r.wh_code === whFilter.value) : invSummary.value);

function resetFilters() {
  whFilter.value = ''; catFilter.value = ''; alertLevel.value = ''; shipStatusFilter.value = '';
}

function onOpenSku(e) { skuId.value = (e.detail && e.detail.sku) || null; }
function onOpenShipment(e) { shipId.value = (e.detail && e.detail.id) || null; }
function onOpenAlert(e) { alertDetail.value = (e.detail && e.detail.alert) || null; }

function openDetail(title, columns, rows) {
  detailModal.value = { title, columns, rows };
}

const shipCols = [
  { key: 'shipment_id', label: '运单' }, { key: 'origin', label: '起' }, { key: 'dest', label: '讫' },
  { key: 'status', label: '状态' }, { key: 'carrier', label: '承运商' },
  { key: 'delay_min', label: '延迟(分)' }, { key: 'exception_type', label: '异常' },
];
const alertCols = [
  { key: 'alert_id', label: '编号' }, { key: 'type', label: '类型' }, { key: 'level', label: '等级' },
  { key: 'status', label: '状态' }, { key: 'description', label: '描述' },
];
const invDiffCols = [
  { key: 'wh_name', label: '仓库' }, { key: 'sku', label: 'SKU' }, { key: 'product_name', label: '商品' },
  { key: 'book_qty', label: '账面' }, { key: 'actual_qty', label: '实际' }, { key: 'diff_qty', label: '差异' },
];
const orderCols = [
  { key: 'order_no', label: '订单' }, { key: 'order_date', label: '日期' }, { key: 'status', label: '状态' },
  { key: 'sku', label: 'SKU' }, { key: 'product_name', label: '商品' }, { key: 'qty', label: '数量' },
  { key: 'amount', label: '金额' }, { key: 'cust_name', label: '客户' }, { key: 'region', label: '区域' },
];
const complaintCols = [
  { key: 'complaint_id', label: '编号' }, { key: 'order_no', label: '订单' }, { key: 'type', label: '类型' },
  { key: 'satisfaction', label: '满意度' }, { key: 'handled', label: '已处理' }, { key: 'date', label: '日期' },
];

async function kpiOrders() {
  openDetail('订单明细（近 300 单）', orderCols, []);
  try { const r = await api.orders(); detailModal.value.rows = r; } catch (e) { detailModal.value.rows = []; }
}
async function kpiComplaints() {
  openDetail('客户投诉明细', complaintCols, []);
  try { const r = await api.complaints(); detailModal.value.rows = r; } catch (e) { detailModal.value.rows = []; }
}
function kpiTransit() { openDetail('在途运单', shipCols, shipments.value.filter((s) => s.status === '在途')); }
function kpiDelayed() { openDetail('延迟运单', shipCols, shipments.value.filter((s) => s.delay_min > 0)); }
function kpiAlerts() { openDetail('异常告警', alertCols, alerts.value); }
function kpiInvDiff() { openDetail('库存差异明细', invDiffCols, inventory.value.filter((r) => r.diff_qty !== 0)); }

const now = ref('');
let clockTimer = null;
let refreshTimer = null;

async function loadAll() {
  loading.value = true;
  loadError.value = '';
  try {
    const [ov, sh, al, inv, sum, ds, st, ot] = await Promise.all([
      api.overview(), api.shipments(), api.alerts(), api.inventory(),
      api.inventorySummary(), api.datasources(), api.shipmentStatus(), api.ordersTrend(),
    ]);
    overview.value = ov;
    shipments.value = sh;
    alerts.value = al;
    inventory.value = inv;
    invSummary.value = sum;
    datasources.value = ds;
    shipStatus.value = st;
    ordersTrend.value = ot;
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    lastUpdated.value = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  } catch (e) {
    loadError.value = '数据加载失败，请确认 API 服务(8503)已启动';
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function tick() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  now.value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

onMounted(() => {
  loadAll();
  tick();
  clockTimer = setInterval(tick, 1000);
  refreshTimer = setInterval(loadAll, 30000);
  window.addEventListener('open-sku', onOpenSku);
  window.addEventListener('open-shipment', onOpenShipment);
  window.addEventListener('open-alert', onOpenAlert);
});
onBeforeUnmount(() => {
  clearInterval(clockTimer);
  clearInterval(refreshTimer);
  window.removeEventListener('open-sku', onOpenSku);
  window.removeEventListener('open-shipment', onOpenShipment);
  window.removeEventListener('open-alert', onOpenAlert);
});
</script>

<template>
  <div class="shell">
    <div class="dashboard">
      <header class="header">
        <h1>物流系统数据集成可视化平台</h1>
        <div class="header-right">
          <span v-if="loading" class="updating">更新中…</span>
          <span v-else class="updating">数据更新于 {{ lastUpdated }}</span>
          <button class="refresh" @click="loadAll">🔄 刷新</button>
          <div class="time">{{ now }}</div>
        </div>
      </header>

      <div v-if="loadError" class="error-bar">{{ loadError }} · <a @click="loadAll">重试</a></div>

      <div class="filter-bar">
        <label>仓库
          <select v-model="whFilter">
            <option value="">全部</option>
            <option v-for="w in whOptions" :key="w.wh_code" :value="w.wh_code">{{ w.wh_name }}</option>
          </select>
        </label>
        <label>品类
          <select v-model="catFilter">
            <option value="">全部</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label>告警等级
          <select v-model="alertLevel">
            <option value="">全部</option><option>高</option><option>中</option><option>低</option>
          </select>
        </label>
        <label>运单状态
          <select v-model="shipStatusFilter">
            <option value="">全部</option><option>在途</option><option>异常</option><option>已签收</option><option>待发运</option>
          </select>
        </label>
        <button class="refresh" @click="resetFilters">重置</button>
      </div>

      <div v-if="overview" class="kpi-row">
        <KpiCard label="订单总数" :value="overview.totalOrders" sub="ERP 接入 · 点我看明细" color="#38bdf8" @click="kpiOrders" />
        <KpiCard label="在途运单" :value="overview.onTransit" sub="实时 GPS 追踪中" color="#22d3ee" @click="kpiTransit" />
        <KpiCard label="运输准时率" :value="(overview.ontimeRate * 100).toFixed(1) + '%'" sub="无延迟运单占比" color="#4ade80" @click="kpiDelayed" />
        <KpiCard label="异常告警" :value="overview.totalAlerts" :sub="'待处理 ' + overview.pendingAlerts" color="#f87171" @click="kpiAlerts" />
        <KpiCard label="库存准确率" :value="(overview.inventoryAccuracy * 100).toFixed(2) + '%'" :sub="'缺货 ' + overview.lowStock + ' 项'" color="#fbbf24" @click="kpiInvDiff" />
        <KpiCard label="客户满意度" :value="overview.avgSatisfaction" sub="CRM 平均分(5分制)" color="#c084fc" @click="kpiComplaints" />
      </div>

      <div class="main-grid">
        <TransitMap :shipments="filteredShipments" />
        <AlertsPanel :alerts="filteredAlerts" />
      </div>

      <div class="sub-grid">
        <InventoryPanel
          :inventory="filteredInventory"
          :summary="filteredSummary"
          :accuracy="overview ? overview.inventoryAccuracy : 1"
          :low-stock="overview ? overview.lowStock : 0"
        />
        <TrendCharts :ship-status="shipStatus" :orders-trend="ordersTrend" />
      </div>

      <DataSourcePanel :datasources="datasources" />
    </div>
    <AiCopilot />
    <SkuDrawer :sku="skuId" @close="skuId = null" />
    <ShipmentDrawer :id="shipId" @close="shipId = null" />
    <AlertDrawer :alert="alertDetail" @close="alertDetail = null" />
    <DetailModal v-if="detailModal" :title="detailModal.title" :columns="detailModal.columns" :rows="detailModal.rows" @close="detailModal = null" />
  </div>
</template>

<style>
.shell { display: flex; width: 100%; min-height: 100vh; }
.shell .dashboard { flex: 1; min-width: 0; }
.header-right { display: flex; align-items: center; gap: 12px; }
.updating { font-size: 12px; color: #93c5fd; }
.refresh { background: rgba(56,189,248,.15); color: #7dd3fc; border: 1px solid rgba(56,189,248,.35);
  border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 12px; }
.error-bar { background: rgba(248,113,113,.12); color: #fca5a5; border: 1px solid rgba(248,113,113,.4);
  border-radius: 8px; padding: 8px 14px; margin-top: 10px; font-size: 13px; }
.error-bar a { color: #fda4af; cursor: pointer; text-decoration: underline; }
.filter-bar { display: flex; gap: 14px; align-items: center; margin-top: 10px; padding: 8px 14px;
  background: rgba(16,58,118,.25); border: 1px solid rgba(56,189,248,.2); border-radius: 8px; flex-wrap: wrap; }
.filter-bar label { font-size: 12px; color: #bae6fd; display: flex; align-items: center; gap: 6px; }
.filter-bar select { background: #060d1f; color: #dbeafe; border: 1px solid rgba(56,189,248,.3);
  border-radius: 6px; padding: 4px 8px; font-size: 12px; }
</style>
