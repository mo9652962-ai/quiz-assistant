<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
import StatusMessage from '../components/StatusMessage.vue'

const items = ref([])
const filter = ref('due')
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try { const data = await api.reviews({ due: filter.value === 'due', wrong: filter.value === 'wrong' }); items.value = data.items } catch (err) { error.value = err.message || '复习列表读取失败。' } finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <section class="page-heading"><p class="eyebrow">REVIEW QUEUE</p><h1>错题复习</h1><p>复习题仍然不携带正确答案，答题记录统一走 practice answer endpoint。</p></section>
  <div class="filter-row"><button class="filter" :class="{ active: filter === 'due' }" @click="filter = 'due'; load()">到期</button><button class="filter" :class="{ active: filter === 'wrong' }" @click="filter = 'wrong'; load()">错题</button></div>
  <StatusMessage v-if="loading" message="正在读取复习队列…" /><StatusMessage v-else-if="error" kind="error" :message="error" />
  <section v-else class="review-list"><article v-for="item in items" :key="item.question.id" class="card review-item"><span class="badge">{{ item.question.bank }}</span><h2>{{ item.question.stem }}</h2><p class="muted">重复 {{ item.repetitions }} 次 · 间隔 {{ item.interval_days }} 天</p><RouterLink class="button ghost" to="/practice">进入练习</RouterLink></article><article v-if="!items.length" class="card empty-state"><h2>队列为空</h2><p>完成几道练习后，这里会出现需要复习的题目。</p></article></section>
</template>
