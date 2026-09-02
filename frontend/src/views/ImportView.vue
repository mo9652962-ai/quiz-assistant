<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import StatusMessage from '../components/StatusMessage.vue'

const file = ref(null)
const preview = ref(null)
const loading = ref(false)
const error = ref('')

function selectFile(event) {
  file.value = event.target.files[0] || null
  preview.value = null
  error.value = ''
}

async function previewImport() {
  if (!file.value) return
  loading.value = true
  error.value = ''
  try { preview.value = await api.importQuestions(file.value, true) } catch (err) { error.value = err.message || '预览失败。' } finally { loading.value = false }
}

async function confirmImport() {
  if (!file.value) return
  loading.value = true
  error.value = ''
  try { preview.value = await api.importQuestions(file.value, false) } catch (err) { error.value = err.message || '导入失败。' } finally { loading.value = false }
}
</script>

<template>
  <section class="page-heading"><p class="eyebrow">IMPORT</p><h1>导入题库</h1><p>先 dry-run 预览拒绝项；确认后才写入本机数据库。不接受 URL 导入。</p></section>
  <article class="card form-card">
    <label for="question-file">JSON / JSONL / CSV 文件</label>
    <input id="question-file" type="file" accept=".json,.jsonl,.csv,application/json,text/csv" @change="selectFile" />
    <div class="action-row"><button class="button primary" :disabled="loading || !file" @click="previewImport">{{ loading ? '处理中…' : '预览（dry-run）' }}</button><button class="button danger" :disabled="loading || !preview || !file" @click="confirmImport">确认写入题库</button></div>
  </article>
  <StatusMessage v-if="error" kind="error" :message="error" />
  <article v-if="preview" class="card result-card">
    <div class="result-top"><span class="badge">{{ preview.dry_run ? '预览结果' : '已写入' }}</span><span>{{ preview.source_name }}</span></div>
    <div class="stats-grid compact"><div><strong>{{ preview.total }}</strong><small>总行数</small></div><div><strong>{{ preview.imported }}</strong><small>可导入</small></div><div><strong>{{ preview.rejected_count }}</strong><small>拒绝</small></div></div>
    <div v-if="preview.rejected.length" class="rejected-list"><h2>拒绝项</h2><div v-for="item in preview.rejected" :key="item.row_number"><strong>第 {{ item.row_number }} 行</strong>{{ item.error }}</div></div>
  </article>
</template>
