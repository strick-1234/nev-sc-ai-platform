<template>
  <div class="panel">
    <div class="panel-title">异常告警与闭环追踪</div>
    <div class="panel-body">
      <div class="alert-stats">
        <span class="badge level-high">高 {{ counts.high }}</span>
        <span class="badge level-mid">中 {{ counts.mid }}</span>
        <span class="badge level-low">低 {{ counts.low }}</span>
        <span class="badge status-pending">待处理 {{ counts.pending }}</span>
        <span class="badge status-processing">处理中 {{ counts.processing }}</span>
        <span class="badge status-closed">已闭环 {{ counts.closed }}</span>
      </div>
      <div class="alert-list">
        <div v-for="a in alerts" :key="a.alert_id" class="alert-item" :style="{ borderLeftColor: levelColor(a.level) }" @click="openAlert(a)">
          <div class="row1">
            <span class="type">{{ a.type }}</span>
            <span>
              <span class="badge" :class="levelClass(a.level)">{{ a.level }}</span>
              <span class="badge" :class="statusClass(a.status)" style="margin-left:4px">{{ a.status }}</span>
            </span>
          </div>
          <div class="desc">{{ a.description }}</div>
          <button class="ask-ai" @click.stop="askAI(a)">🤖 问 AI</button>
        </div>
        <div v-if="!alerts.length" class="desc">暂无告警</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({ alerts: { type: Array, default: () => [] } });

const counts = computed(() => ({
  high: props.alerts.filter((a) => a.level === '高').length,
  mid: props.alerts.filter((a) => a.level === '中').length,
  low: props.alerts.filter((a) => a.level === '低').length,
  pending: props.alerts.filter((a) => a.status === '待处理').length,
  processing: props.alerts.filter((a) => a.status === '处理中').length,
  closed: props.alerts.filter((a) => a.status === '已闭环').length,
}));

const levelClass = (l) => (l === '高' ? 'level-high' : l === '中' ? 'level-mid' : 'level-low');
const statusClass = (s) => (s === '待处理' ? 'status-pending' : s === '处理中' ? 'status-processing' : 'status-closed');
const levelColor = (l) => (l === '高' ? '#f87171' : l === '中' ? '#fbbf24' : '#60a5fa');

function askAI(a) {
  window.dispatchEvent(new CustomEvent('ask-ai', {
    detail: { text: `告警「${a.type}·${a.level}」：${a.description}，该怎么处理？` },
  }));
}

function openAlert(a) {
  window.dispatchEvent(new CustomEvent('open-alert', { detail: { alert: a } }));
}
</script>

<style scoped>
.alert-stats { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.alert-item { cursor: pointer; }
.ask-ai { margin-top: 6px; background: rgba(56,189,248,.12); color: #7dd3fc; border: 1px solid rgba(56,189,248,.35);
  border-radius: 5px; padding: 2px 8px; font-size: 11px; cursor: pointer; }
</style>
