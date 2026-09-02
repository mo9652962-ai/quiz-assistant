<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import StatusMessage from '../components/StatusMessage.vue'

const text = ref('')
const bank = ref('')
const result = ref(null)
const loading = ref(false)
const error = ref('')

async function search() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await api.query({ text: text.value, bank: bank.value || null, reveal: 'candidate' })
  } catch (err) {
    error.value = err.message || '查询失败。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="page-heading"><p class="eyebrow">SEARCH / ANSWER</p><h1>查询答案</h1><p>高置信度结果可直接显示；其余结果只展示候选、分数与证据。</p></section>
  <form class="card form-card" @submit.prevent="search">
    <label for="question-text">题干</label>
    <textarea id="question-text" v-model="text" required rows="4" placeholder="粘贴题干或题目片段…"></textarea>
    <label for="search-bank">题库（可选）</label>
    <input id="search-bank" v-model="bank" placeholder="例如 english-basic" />
    <button class="button primary" :disabled="loading || !text.trim()">{{ loading ? '查询中…' : '查询' }}</button>
  </form>
  <StatusMessage v-if="error" kind="error" :message="error" />
  <article v-if="result" class="card result-card">
    <div class="result-top"><span class="badge" :class="`badge-${result.status}`">{{ result.status }}</span><span>score {{ result.score.toFixed(2) }}</span></div>
    <h2 v-if="result.answer_texts.length">高置信度候选</h2>
    <h2 v-else>需要确认</h2>
    <div v-if="result.answer_texts.length" class="answer-list"><div v-for="(answer, index) in result.answer_texts" :key="answer"><strong>{{ result.answer_keys[index] }}</strong>{{ answer }}</div></div>
    <p v-else class="muted">未自动披露正确答案。请核对候选题目与证据后再决定下一步。</p>
    <dl class="evidence"><div><dt>匹配方法</dt><dd>{{ result.method }}</dd></div><div><dt>证据</dt><dd>{{ result.evidence.join('；') || '暂无' }}</dd></div></dl>
  </article>
</template>
