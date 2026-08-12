<template>
  <div class="layout">
    <header class="topbar">
      <router-link to="/" class="brand">AI 热点分析</router-link>
      <nav>
        <router-link to="/">首页</router-link>
        <router-link to="/history">历史检索</router-link>
        <router-link to="/settings">设置</router-link>
        <a
          v-if="collectorStaticUrl"
          class="collector-link"
          :href="collectorStaticUrl"
          target="_blank"
          rel="noopener noreferrer"
        >
          采集控制台
        </a>
      </nav>
    </header>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from './api'

const collectorBaseUrl = ref('')

const collectorStaticUrl = computed(() => {
  const base = collectorBaseUrl.value.trim().replace(/\/+$/, '')
  return base ? `${base}/static/` : '' 
})

onMounted(async () => {
  try {
    const settings = await api.getSettings()
    collectorBaseUrl.value = settings.collector.base_url || ''
  } catch {
    collectorBaseUrl.value = ''
  }
})
</script>
