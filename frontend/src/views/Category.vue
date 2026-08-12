<template>
  <div class="page">
    <section class="hero-panel compact">
      <div class="hero-copy">
        <p class="eyebrow">分类浏览</p>
        <h1>{{ name }}</h1>
        <p class="lead">{{ date }} · 共 {{ items.length }} 条</p>
      </div>
      <div class="filters">
        <input type="date" v-model="date" :max="today" @change="onDateChange" />
        <router-link :to="homeLink" class="linkish">返回首页</router-link>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <div class="card-grid" v-if="items.length">
      <HotCard v-for="item in items" :key="item.hot_id" :item="item" />
    </div>
    <p v-else-if="!loading" class="muted">该分类暂无热点</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, todayISO, type HotItem } from '../api'
import HotCard from '../components/HotCard.vue'

const props = defineProps<{ name: string }>()
const route = useRoute()
const router = useRouter()
const today = todayISO()

function normalizeDate(value: unknown): string | null {
  if (typeof value !== 'string') return null
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const d = new Date(`${value}T00:00:00`)
  if (Number.isNaN(d.getTime())) return null
  return value > today ? today : value
}

const date = ref(normalizeDate(route.query.date) || today)
const items = ref<HotItem[]>([])
const loading = ref(false)
const error = ref('')

const homeLink = computed(() =>
  date.value === today ? '/' : { path: '/', query: { date: date.value } },
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    items.value = await api.byCategory(props.name, date.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function onDateChange() {
  const next = normalizeDate(date.value) || today
  date.value = next
  router.replace({
    query: next === today ? {} : { date: next },
  })
  load()
}

watch(() => props.name, load)
watch(
  () => route.query.date,
  (q) => {
    const fromRoute = normalizeDate(q) || today
    if (fromRoute !== date.value) {
      date.value = fromRoute
      load()
    }
  },
)
onMounted(load)
</script>
