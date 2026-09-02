<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
import StatusMessage from '../components/StatusMessage.vue'

const loading = ref(true)
const error = ref('')
const health = ref(null)
const banks = ref([])
const reviews = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [healthResult, bankResult, reviewResult] = await Promise.all([
      api.health(), api.banks(), api.reviews({ due: true, limit: 5 }),
    ])
    health.value = healthResult
    banks.value = bankResult.items
    reviews.value = reviewResult
  } catch (err) {
    error.value = err.message || '无法连接本机 API，请确认服务已启动。'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="hero">
    <div>
      <p class="eyebrow">LOCAL-FIRST PRACTICE</p>
      <h1>今天，先做一道题。</h1>
      <p class="lead">题库、练习记录和复习节奏留在本机；答案只在用户主动提交后披露。</p>
    </div>
    <RouterLink class="button primary" to="/practice">开始练习</RouterLink>
  </section>

  <StatusMessage v-if="loading" message="正在读取本机题库…" />
  <StatusMessage v-else-if="error" kind="error" :message="error" />

  <template v-else>
    <section class="stats-grid" aria-label="题库状态">
      <article class="card stat-card"><span>服务状态</span><strong>{{ health?.status === 'ok' ? '正常' : '降级' }}</strong><small>schema v{{ health?.schema_version }}</small></article>
      <article class="card stat-card"><span>题库</span><strong>{{ banks.length }}</strong><small>个可用题库</small></article>
      <article class="card stat-card"><span>待复习</span><strong>{{ reviews?.total || 0 }}</strong><small>道到期题目</small></article>
    </section>

    <section class="content-grid">
      <article class="card">
        <div class="card-heading"><div><p class="eyebrow">QUESTION BANKS</p><h2>题库</h2></div><RouterLink to="/import">导入</RouterLink></div>
        <div v-if="banks.length" class="bank-list">
          <div v-for="bank in banks" :key="bank.name" class="bank-row"><span>{{ bank.name }}</span><small>{{ bank.active_count }} / {{ bank.question_count }} 道有效题</small></div>
        </div>
        <p v-else class="empty">暂无题库。可以先进行 dry-run 导入预览。</p>
      </article>
      <article class="card accent-card">
        <p class="eyebrow">SAFE BY DEFAULT</p>
        <h2>每一步都可回看</h2>
        <p>练习开始时不发送正确答案；查询结果保留匹配分数和证据；备份恢复需要显式确认。</p>
        <RouterLink class="text-link" to="/settings">检查备份设置 →</RouterLink>
      </article>
    </section>
  </template>
</template>
