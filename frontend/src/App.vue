<template>
  <div class="layout">
    <header class="topbar">
      <router-link to="/" class="brand">AI 热点分析</router-link>
      <div class="topbar-end">
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
        <ThemeSwitch />
      </div>
    </header>
    <main class="main">
      <router-view v-slot="{ Component }">
        <Transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from './api'
import ThemeSwitch from './components/ThemeSwitch.vue'
import { useTheme } from './composables/useTheme'

useTheme()

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

<style>
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
@media (prefers-reduced-motion: reduce) {
  .page-fade-enter-active,
  .page-fade-leave-active {
    transition: none;
  }
}
</style>
