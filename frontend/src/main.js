import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import DashboardView from './views/DashboardView.vue'
import ImportView from './views/ImportView.vue'
import SearchView from './views/SearchView.vue'
import PracticeView from './views/PracticeView.vue'
import ReviewView from './views/ReviewView.vue'
import SettingsView from './views/SettingsView.vue'
import './styles.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: DashboardView },
    { path: '/import', component: ImportView },
    { path: '/search', component: SearchView },
    { path: '/practice', component: PracticeView },
    { path: '/review', component: ReviewView },
    { path: '/settings', component: SettingsView },
  ],
})

createApp(App).use(router).mount('#app')
