<script setup>
import { ref, watch } from 'vue';
import { api } from '../api';

const props = defineProps({ id: String });
const emit = defineEmits(['close']);
const detail = ref(null);

watch(() => props.id, async (id) => {
  if (!id) { detail.value = null; return; }
  detail.value = null;
  try {
    detail.value = await api.shipmentDetail(id);
  } catch (e) {
    detail.value = { shipment: { shipment_id: id }, error: e.message };
  }
});
</script>

<template>
  <div v-if="id" class="overlay" @click.self="emit('close')">
    <aside class="drawer">
      <div class="d-head">
        <div>
          <div class="d-title">{{ detail && detail.shipment ? detail.shipment.shipment_id : id }}</div>
          <div class="d-sub">{{ detail && detail.shipment ? detail.shipment.origin + ' → ' + detail.shipment.dest : '' }}</div>
        </div>
        <button class="x" @click="emit('close')">✕</button>
      </div>

      <div v-if="detail && detail.error" class="d-body"><p>{{ detail.error }}</p></div>
      <div v-else-if="detail && detail.shipment" class="d-body">
        <div class="kv-grid">
          <div><b>承运商</b>{{ detail.shipment.carrier }}</div>
          <div><b>状态</b>{{ detail.shipment.status }}</div>
          <div><b>里程</b>{{ detail.shipment.distance }} km</div>
          <div><b>延迟</b><span :style="{color: detail.shipment.delay_min > 0 ? '#f87171' : '#4ade80'}">{{ detail.shipment.delay_min }} 分钟</span></div>
          <div><b>异常</b>{{ detail.shipment.exception_type || '无' }}</div>
          <div><b>发车</b>{{ detail.shipment.depart_time }}</div>
        </div>

        <div v-if="detail.order" class="sec">
          <div class="sec-title">关联订单</div>
          <div class="kv-grid">
            <div><b>订单</b>{{ detail.order.order_no }}</div>
            <div><b>商品</b>{{ detail.order.product_name }}</div>
            <div><b>数量</b>{{ detail.order.qty }}</div>
            <div><b>金额</b>{{ detail.order.amount }}</div>
            <div><b>客户</b>{{ detail.order.cust_name }}</div>
            <div><b>区域</b>{{ detail.order.region }}</div>
          </div>
        </div>

        <div v-if="detail.complaints.length" class="sec">
          <div class="sec-title">关联投诉</div>
          <div v-for="c in detail.complaints" :key="c.complaint_id" class="ib">
            {{ c.type }} · 满意度 {{ c.satisfaction }} · {{ c.handled ? '已处理' : '未处理' }}
          </div>
        </div>

        <div v-if="detail.freight" class="sec">
          <div class="sec-title">运费结算</div>
          <div class="kv-grid">
            <div><b>基础运费</b>{{ detail.freight.base_fee }}</div>
            <div><b>燃油附加</b>{{ detail.freight.fuel_fee }}</div>
            <div><b>合计</b>{{ detail.freight.total }}</div>
            <div><b>结算</b>{{ detail.freight.settle_status }}</div>
          </div>
        </div>

        <div class="sec">
          <div class="sec-title">轨迹回放（{{ detail.tracking.length }} 点）</div>
          <table>
            <thead><tr><th>#</th><th>时间</th><th>事件</th><th>经纬度</th></tr></thead>
            <tbody>
              <tr v-for="t in detail.tracking" :key="t.seq">
                <td>{{ t.seq }}</td><td>{{ t.ts }}</td><td>{{ t.event }}</td><td>{{ t.lng }}, {{ t.lat }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;display:flex;justify-content:flex-end;}
.drawer{width:500px;max-width:94vw;height:100vh;background:#0b1e3a;border-left:1px solid rgba(56,189,248,.35);display:flex;flex-direction:column;}
.d-head{display:flex;justify-content:space-between;align-items:center;padding:16px;border-bottom:1px solid rgba(56,189,248,.25);}
.d-title{font-size:18px;font-weight:700;color:#e0f2fe;}
.d-sub{font-size:12px;color:#93c5fd;margin-top:3px;}
.x{background:none;border:none;color:#9ec8f5;font-size:18px;cursor:pointer;}
.d-body{flex:1;overflow:auto;padding:14px 16px;}
.kv-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;color:#dbeafe;}
.kv-grid b{color:#7dd3fc;margin-right:4px;}
.sec{margin-top:14px;}
.sec-title{font-size:13px;color:#7dd3fc;margin-bottom:6px;}
table{width:100%;border-collapse:collapse;font-size:12px;color:#dbeafe;}
th,td{padding:6px 8px;border-bottom:1px solid rgba(56,189,248,.15);text-align:left;}
th{color:#7dd3fc;}
.ib{font-size:13px;color:#dbeafe;margin:4px 0;}
</style>
