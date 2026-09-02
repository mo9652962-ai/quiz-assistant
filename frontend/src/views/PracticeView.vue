<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import StatusMessage from '../components/StatusMessage.vue'

const session = ref(null)
const currentIndex = ref(0)
const selected = ref([])
const shortAnswer = ref('')
const result = ref(null)
const autoAnswerMessage = ref('')
const loading = ref(false)
const error = ref('')
const current = computed(() => session.value?.questions[currentIndex.value] || null)
const isMultiple = computed(() => current.value?.type === 'multiple_choice')

async function start() {
  loading.value = true
  error.value = ''
  result.value = null
  autoAnswerMessage.value = ''
  selected.value = []
  shortAnswer.value = ''
  try {
    session.value = await api.startPractice({ count: 10, mode: 'practice' })
    currentIndex.value = 0
  } catch (err) {
    error.value = err.message || '无法开始练习。'
  } finally {
    loading.value = false
  }
}

async function autoAnswer() {
  if (!current.value) return
  loading.value = true
  autoAnswerMessage.value = ''
  try {
    const match = await api.query({
      text: current.value.stem,
      options: current.value.options.map((option) => `${option.key}. ${option.text}`),
      reveal: 'candidate',
    })
    if (!match.auto_answerable || !match.answer_keys.length) {
      autoAnswerMessage.value = '本地题库无法给出高置信度答案，请人工确认后作答。'
      return
    }
    selected.value = [...match.answer_keys]
    autoAnswerMessage.value = '已填入本地题库的高置信度答案；请检查后再提交。'
  } catch (err) {
    autoAnswerMessage.value = err.message || '自动匹配失败，请手动作答。'
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!current.value || !session.value) return
  loading.value = true
  error.value = ''
  try {
    const answer = isMultiple.value ? selected.value.join(',') : (selected.value[0] || shortAnswer.value)
    result.value = await api.submitAnswer(session.value.id, {
      question_id: current.value.id,
      answer,
      reveal_answer: true,
    })
  } catch (err) {
    error.value = err.message || '提交失败。'
  } finally {
    loading.value = false
  }
}

function next() {
  if (!session.value || currentIndex.value >= session.value.questions.length - 1) return
  currentIndex.value += 1
  selected.value = []
  shortAnswer.value = ''
  result.value = null
}

onMounted(start)
</script>

<template>
  <section class="page-heading"><p class="eyebrow">PRACTICE SESSION</p><h1>开始练习</h1><p>先选择你的答案，提交后才会显示对错与解析。</p></section>
  <StatusMessage v-if="error" kind="error" :message="error" />
  <StatusMessage v-if="loading && !current" message="正在准备练习…" />
  <article v-if="current" class="card practice-card">
    <div class="progress-line"><span>第 {{ currentIndex + 1 }} / {{ session.questions.length }} 题</span><span>{{ current.bank }}</span></div>
    <h2>{{ current.stem }}</h2>
    <div v-if="current.options.length" class="options" role="group" aria-label="答案选项">
      <label v-for="option in current.options" :key="option.key" class="option-row">
        <input v-if="isMultiple" v-model="selected" type="checkbox" :value="option.key" />
        <input v-else :checked="selected.includes(option.key)" type="radio" name="practice-answer" :value="option.key" @change="selected = [option.key]" />
        <span><strong>{{ option.key }}</strong>{{ option.text }}</span>
      </label>
    </div>
    <input v-else v-model="shortAnswer" class="short-answer" aria-label="答案" placeholder="输入答案" />
    <div class="action-row"><button class="button primary" :disabled="loading || (!selected.length && !shortAnswer.trim())" @click="submit">{{ loading ? '提交中…' : '提交答案' }}</button><button class="button ghost" :disabled="loading" @click="autoAnswer">本地自动匹配</button><button class="button ghost" @click="start">重新开始</button></div>
    <p v-if="autoAnswerMessage" class="muted auto-answer-message">{{ autoAnswerMessage }}</p>
    <section v-if="result" class="feedback" :class="result.is_correct ? 'feedback-good' : 'feedback-bad'">
      <strong>{{ result.is_correct ? '回答正确' : '回答错误' }}</strong>
      <p v-if="result.explanation">{{ result.explanation }}</p>
      <div v-if="result.correct_keys?.length" class="revealed-answer">正确答案：{{ result.correct_keys.join('、') }}</div>
      <button v-if="currentIndex < session.questions.length - 1" class="text-button" @click="next">下一题 →</button>
    </section>
  </article>
  <article v-else-if="!loading && !error" class="card empty-state"><h2>题库暂无可练习题目</h2><p>请先导入一个有效题库。</p></article>
</template>
