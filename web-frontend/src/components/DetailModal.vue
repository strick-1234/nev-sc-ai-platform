<script setup>
defineProps({
  title: String,
  columns: { type: Array, default: () => [] },   // [{key, label}]
  rows: { type: Array, default: () => [] },
});
defineEmits(['close']);
</script>

<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="m-head">
        <b>{{ title }}</b>
        <button class="x" @click="$emit('close')">✕</button>
      </div>
      <div class="m-body">
        <table>
          <thead><tr><th v-for="c in columns" :key="c.key">{{ c.label }}</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in rows" :key="i">
              <td v-for="c in columns" :key="c.key">{{ r[c.key] }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!rows.length" class="dim">加载中或无数据…</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:888;display:flex;align-items:center;justify-content:center;}
.modal{width:820px;max-width:94vw;max-height:82vh;display:flex;flex-direction:column;background:#0b1e3a;border:1px solid rgba(56,189,248,.4);border-radius:12px;}
.m-head{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;color:#e0f2fe;border-bottom:1px solid rgba(56,189,248,.2);}
.x{background:none;border:none;color:#9ec8f5;font-size:18px;cursor:pointer;}
.m-body{flex:1;overflow:auto;padding:12px 16px;}
table{width:100%;border-collapse:collapse;font-size:12px;color:#dbeafe;}
th,td{padding:6px 8px;border-bottom:1px solid rgba(56,189,248,.15);text-align:left;white-space:nowrap;}
th{color:#7dd3fc;position:sticky;top:0;background:#0b1e3a;}
.dim{color:#8b9db8;font-size:13px;padding:10px 0;}
</style>
