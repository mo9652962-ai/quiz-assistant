<script setup>
defineProps({
  kind: { type: String, default: 'info' },
  message: { type: String, required: true },
})
</script>

<template>
  <p class="status-message" :class="`status-${kind}`" role="status">{{ message }}</p>
</template>
