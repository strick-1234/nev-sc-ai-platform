<script setup>
const props = defineProps({ alert: Object });
const emit = defineEmits(['close']);

function askAI() {
  const a = props.alert;
  window.dispatchEvent(new CustomEvent('ask-ai', {
    detail: { text: `告警「${a.type}·${a.level}」：${a.description}，该怎么处理？` },
  }));
}
</script>

<template>
  <div v-if="alert" class="overlay" @click.self="emit('close')">
    <aside class="drawer">
      <div class="d-head">
        <div>
          <div class="d-title">🚨 {{ alert.type }}</div>
          <div class="d-sub">等级 {{ alert.level }} · {{ alert.status }}</div>
        </div>
        <button class="x" @click="emit('close')">✕</button>
      </div>
      <div class="d-body">
        <div class="desc">{{ alert.description }}</div>

        <div class="sec">
          <div class="sec-title">处置建议</div>
          <div class="sugg">{{ alert.suggestion || '—' }}</div>
        </div>
        <div class="sec">
          <div class="sec-title">升级路径</div>
          <div class="sugg">{{ alert.escalation || '—' }}</div>
        </div>

        <div class="sec kv">
          <div><b>来源</b>{{ alert.source }}</div>
          <div><b>关联</b>{{ alert.ref_id }}</div>
          <div><b>时间</b>{{ alert.create_time }}</div>
        </div>

        <button class="ask" @click="askAI">🤖 问 AI 怎么处理</button>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;display:flex;justify-content:flex-end;}
.drawer{width:420px;max-width:94vw;height:100vh;background:#0b1e3a;border-left:1px solid rgba(56,189,248,.35);display:flex;flex-direction:column;}
.d-head{display:flex;justify-content:space-between;align-items:center;padding:16px;border-bottom:1px solid rgba(56,189,248,.25);}
.d-title{font-size:18px;font-weight:700;color:#fda4af;}
.d-sub{font-size:12px;color:#93c5fd;margin-top:3px;}
.x{background:none;border:none;color:#9ec8f5;font-size:18px;cursor:pointer;}
.d-body{flex:1;overflow:auto;padding:14px 16px;}
.desc{font-size:14px;color:#dbeafe;line-height:1.6;padding:10px 12px;background:rgba(255,255,255,.04);border-radius:8px;}
.sec{margin-top:14px;}
.sec-title{font-size:13px;color:#7dd3fc;margin-bottom:6px;}
.sugg{font-size:13px;color:#dbeafe;padding:10px 12px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.2);border-radius:8px;line-height:1.6;}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;color:#dbeafe;}
.kv b{color:#7dd3fc;margin-right:4px;}
.ask{margin-top:16px;width:100%;background:#0ea5e9;color:#fff;border:none;border-radius:8px;padding:10px;cursor:pointer;font-size:13px;}
</style>
