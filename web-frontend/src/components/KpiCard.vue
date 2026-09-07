<template>
  <div class="kpi-card" :style="{ '--accent': color }" @click="$emit('click')">
    <div class="kpi-value" :style="{ color }">{{ value }}</div>
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-sub">{{ sub }}</div>
  </div>
</template>

<script setup>
defineProps({
  value: { type: [String, Number], default: 0 },
  label: String,
  sub: String,
  color: { type: String, default: '#38bdf8' },
});
defineEmits(['click']);
</script>

<style scoped>
.kpi-card { cursor: pointer; }
.kpi-card:hover { border-color: var(--accent); }
</style>
