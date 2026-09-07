<template>
  <div class="panel">
    <div class="panel-title">数据源接入状态监控（5 套异构系统）</div>
    <div class="panel-body">
      <div class="ds-strip">
        <div v-for="d in datasources" :key="d.id" class="ds-card">
          <div class="name">{{ d.name }}</div>
          <div class="row"><span>格式</span><b>{{ d.format }}</b></div>
          <div class="row"><span>更新频率</span><b>{{ d.update }}</b></div>
          <div class="row"><span>接入方式</span><b>{{ d.access }}</b></div>
          <div class="row"><span>数据量</span><b>{{ d.records }} 条</b></div>
          <div class="row"><span>状态</span><b style="color:#4ade80">● {{ d.status }}</b></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ datasources: { type: Array, default: () => [] } });
</script>
