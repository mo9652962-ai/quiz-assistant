<script setup>
import { ref } from 'vue'
import { api } from '../api/client'
import StatusMessage from '../components/StatusMessage.vue'

const backupId = ref('')
const confirm = ref('')
const force = ref(false)
const result = ref(null)
const loading = ref(false)
const error = ref('')

async function createBackup() { loading.value = true; error.value = ''; try { result.value = await api.backup({ action: 'create' }) } catch (err) { error.value = err.message || '备份失败。' } finally { loading.value = false } }
async function restoreBackup() { loading.value = true; error.value = ''; try { result.value = await api.backup({ action: 'restore', backup_id: backupId.value, confirm: confirm.value, force: force.value }) } catch (err) { error.value = err.message || '恢复失败。' } finally { loading.value = false } }
</script>

<template>
  <section class="page-heading"><p class="eyebrow">SETTINGS / BACKUP</p><h1>设置与备份</h1><p>恢复会覆盖当前数据库，必须输入精确确认词；没有确认时服务端拒绝。</p></section>
  <div class="content-grid">
    <article class="card form-card"><p class="eyebrow">SNAPSHOT</p><h2>创建备份</h2><p class="muted">生成受校验的本地备份并返回 backup id。</p><button class="button primary" :disabled="loading" @click="createBackup">创建备份</button></article>
    <article class="card form-card"><p class="eyebrow">RESTORE</p><h2>恢复数据库</h2><label for="backup-id">Backup ID</label><input id="backup-id" v-model="backupId" placeholder="例如 20260902T080000Z" /><label for="restore-confirm">输入 RESTORE_CURRENT_DATABASE</label><input id="restore-confirm" v-model="confirm" autocomplete="off" /><label class="check-row"><input v-model="force" type="checkbox" />确认覆盖当前数据库</label><button class="button danger" :disabled="loading || !backupId || confirm !== 'RESTORE_CURRENT_DATABASE' || !force" @click="restoreBackup">恢复并覆盖</button></article>
  </div>
  <StatusMessage v-if="error" kind="error" :message="error" />
  <article v-if="result" class="card result-card"><span class="badge">{{ result.action === 'create' ? '备份已创建' : '恢复已完成' }}</span><h2>{{ result.backup_id }}</h2><p class="muted">校验状态：{{ result.verified ? '通过' : '未通过' }}<span v-if="result.sha256"> · SHA-256 {{ result.sha256 }}</span></p></article>
</template>
