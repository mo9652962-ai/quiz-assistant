<script setup>
import { RouterLink, RouterView } from 'vue-router'

const links = [
  { to: '/', label: '总览' },
  { to: '/search', label: '查询答案' },
  { to: '/practice', label: '开始练习' },
  { to: '/review', label: '错题复习' },
  { to: '/import', label: '导入题库' },
  { to: '/ocr', label: '截图识别' },
  { to: '/settings', label: '设置与备份' },
]
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">题</span>
        <span><strong>Quiz Assistant</strong><small>本地优先 · 可控披露</small></span>
      </RouterLink>
      <nav aria-label="主导航">
        <RouterLink v-for="link in links" :key="link.to" :to="link.to">{{ link.label }}</RouterLink>
      </nav>
    </header>
    <main class="page-wrap">
      <RouterView />
    </main>
  </div>
</template>
