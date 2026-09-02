<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import StatusMessage from '../components/StatusMessage.vue'

const files = ref([])
const result = ref(null)
const loading = ref(false)
const error = ref('')

function selectFiles(event) {
  files.value = [...event.target.files]
  result.value = null
  error.value = ''
}

async function recognize() {
  if (!files.value.length) return
  loading.value = true
  error.value = ''
  try {
    result.value = await api.ocrRecognize(files.value)
  } catch (err) {
    error.value = err.message || 'OCR 识别失败。请确认已安装 OCR 运行时。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="page-heading">
    <p class="eyebrow">SCREENSHOT / OCR</p>
    <h1>截图识别</h1>
    <p>一次选择多张题目截图；识别结果先校验，只有高置信度结构才允许进入本地匹配。</p>
  </section>
  <article class="card form-card">
    <label for="ocr-files">题目截图（最多 10 张，单张不超过 10 MiB）</label>
    <input id="ocr-files" type="file" multiple accept="image/png,image/jpeg,image/webp,image/bmp" @change="selectFiles" />
    <p class="muted">{{ files.length ? `已选择 ${files.length} 张图片` : '未选择图片' }}</p>
    <button class="button primary" :disabled="loading || !files.length" @click="recognize">
      {{ loading ? '识别中…' : '开始本地 OCR' }}
    </button>
  </article>
  <StatusMessage v-if="error" kind="error" :message="error" />
  <section v-if="result" class="ocr-results">
    <article v-for="item in result.items" :key="item.source_name" class="card">
      <div class="result-top"><span class="badge">{{ item.source_name }}</span><span>{{ item.questions.length }} 道题</span></div>
      <pre class="ocr-text">{{ item.recognized_text }}</pre>
      <div v-for="question in item.questions" :key="`${item.source_name}-${question.number}`" class="ocr-question">
        <div class="result-top"><strong>第 {{ question.number }} 题</strong><span class="badge" :class="`badge-${question.status}`">{{ question.status }}</span></div>
        <p>{{ question.stem || '未识别到题干' }}</p>
        <ul class="ocr-options"><li v-for="option in question.options" :key="option.key"><strong>{{ option.key }}.</strong> {{ option.text }}</li></ul>
        <p class="muted">结构置信度：{{ question.confidence.toFixed(2) }}；{{ question.fill_allowed ? '允许进入本地匹配' : '必须人工校对' }}</p>
        <p v-if="question.issues.length" class="muted">问题：{{ question.issues.join('；') }}</p>
      </div>
    </article>
  </section>
</template>
