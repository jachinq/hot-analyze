<template>
  <div class="page">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">{{ selectedDate }}</p>
        <h1>{{ isToday ? '今日热点总览' : '历史热点总览' }}</h1>
        <p class="lead">
          {{
            report?.summary ||
            stats?.report_summary ||
            (loading ? '加载中…' : '该日期暂无日报，可手动触发分析或等待定时任务')
          }}
        </p>
        <div class="date-switcher">
          <button type="button" class="date-nav" :disabled="loading || analyzing" @click="shiftDate(-1)" title="前一天">
            ‹
          </button>
          <label class="date-picker">
            <span class="sr-only">选择日期</span>
            <input
              type="date"
              v-model="selectedDate"
              :max="today"
              :disabled="analyzing"
              @change="onDatePicked"
            />
          </label>
          <button
            type="button"
            class="date-nav"
            :disabled="loading || analyzing || isToday"
            @click="shiftDate(1)"
            title="后一天"
          >
            ›
          </button>
          <button
            v-if="!isToday"
            type="button"
            class="ghost"
            :disabled="loading || analyzing"
            @click="goToday"
          >
            回到今天
          </button>
        </div>

        <div class="analyze-bar">
          <button
            type="button"
            class="analyze-btn"
            :disabled="loading || analyzing"
            @click="startAnalyze(false)"
          >
            {{ analyzing ? '分析中…' : '手动分析' }}
          </button>
          <button
            v-if="stats?.has_report && !analyzing"
            type="button"
            class="ghost"
            :disabled="loading"
            @click="startAnalyze(true)"
            title="忽略已有结果，重新调用 AI"
          >
            强制重跑
          </button>
          <p class="analyze-hint">
            <template v-if="analyzing">
              {{ jobHint || '任务已提交，正在拉取热点并生成总结…' }}
            </template>
            <template v-else-if="stats?.has_report">
              该日已有分析，再次运行会跳过已总结条目，仅补全新增热点并刷新日报
            </template>
            <template v-else>
              按当前日期触发 AI 总结；已有条目会自动跳过
            </template>
          </p>
        </div>

        <p v-if="analyzeMsg" class="hint" :class="{ ok: analyzeOk }">{{ analyzeMsg }}</p>
        <p v-if="stats && !stats.has_report && !analyzing" class="hint">
          任务状态：{{ stats.job_status || '未运行' }}
          <button class="linkish" @click="loadLatestFallback">查看最近日报</button>
        </p>
      </div>
      <div class="stat-block">
        <div class="stat">
          <strong>{{ stats?.hot_count ?? '—' }}</strong>
          <span>热点条数</span>
        </div>
        <div class="stat">
          <strong>{{ stats?.categories?.length ?? 0 }}</strong>
          <span>覆盖分类</span>
        </div>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading" class="muted">加载中…</p>

    <section class="grid-2" v-if="stats && !loading">
      <div class="panel">
        <h2>分类分布</h2>
        <div class="bars" v-if="stats.categories.length">
          <div v-for="c in stats.categories" :key="c.category" class="bar-row">
            <router-link
              class="bar-label"
              :to="{
                path: `/category/${encodeURIComponent(c.category)}`,
                query: { date: selectedDate },
              }"
            >
              {{ c.category }}
            </router-link>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: barWidth(c.count) }"></div>
            </div>
            <span class="bar-count">{{ c.count }}</span>
          </div>
        </div>
        <p v-else class="muted">暂无分类数据</p>
      </div>

      <div class="panel">
        <h2>重要性排行</h2>
        <ol class="rank-list" v-if="ranking.length">
          <li v-for="(item, idx) in ranking.slice(0, 10)" :key="item.hot_id">
            <span class="rank-idx">{{ idx + 1 }}</span>
            <div>
              <div class="rank-title">{{ item.title }}</div>
              <div class="muted">{{ item.category }} · 重要性 {{ item.importance }}</div>
            </div>
          </li>
        </ol>
        <p v-else class="muted">暂无排行</p>
      </div>
    </section>

    <section class="panel" v-if="!loading && report?.content?.highlights?.length">
      <h2>重点摘要</h2>
      <ul class="highlight-list">
        <li v-for="(h, i) in report.content.highlights" :key="`${h.title}-${i}`">
          <div class="highlight-head">
            <strong>{{ h.title }}</strong>
            <span v-if="h.impact != null" class="muted">影响 {{ h.impact }}</span>
          </div>
          <p class="muted">{{ h.summary }}</p>
        </li>
      </ul>
    </section>

    <section class="panel" v-if="!loading && report?.content?.trends?.length">
      <h2>趋势观察</h2>
      <ul class="trend-list">
        <li v-for="(t, i) in report.content.trends" :key="i">{{ t }}</li>
      </ul>
    </section>

    <section class="panel" v-if="!loading && report?.content?.markdown">
      <h2>AI 日报</h2>
      <div class="markdown" v-html="markdownHtml"></div>
    </section>

    <section class="panel" v-if="!loading && report?.items?.length">
      <h2>热点列表</h2>
      <div class="card-grid">
        <HotCard v-for="item in report.items.slice(0, 24)" :key="item.hot_id" :item="item" />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import { api, todayISO, type HotItem, type Report, type TodayStats } from '../api'
import HotCard from '../components/HotCard.vue'

const POLL_MS = 2500
const POLL_MAX = 120

const route = useRoute()
const router = useRouter()
const today = todayISO()

const selectedDate = ref(normalizeDate(route.query.date) || today)
const loading = ref(true)
const analyzing = ref(false)
const error = ref('')
const analyzeMsg = ref('')
const analyzeOk = ref(false)
const jobHint = ref('')
const stats = ref<TodayStats | null>(null)
const report = ref<Report | null>(null)
const ranking = ref<HotItem[]>([])

let pollTimer: ReturnType<typeof setTimeout> | null = null
let pollCount = 0

const isToday = computed(() => selectedDate.value === today)

const maxCat = computed(() =>
  Math.max(1, ...(stats.value?.categories.map((c) => c.count) || [1])),
)

function barWidth(count: number) {
  return `${Math.round((count / maxCat.value) * 100)}%`
}

const markdownHtml = computed(() => {
  const md = report.value?.content?.markdown || ''
  return marked.parse(md, { async: false }) as string
})

function normalizeDate(value: unknown): string | null {
  if (typeof value !== 'string') return null
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const d = new Date(`${value}T00:00:00`)
  if (Number.isNaN(d.getTime())) return null
  return value
}

function shiftISO(base: string, deltaDays: number): string {
  const d = new Date(`${base}T00:00:00`)
  d.setDate(d.getDate() + deltaDays)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function syncQuery(date: string) {
  const nextQuery = date === today ? {} : { date }
  router.replace({ query: nextQuery })
}

function stopPoll() {
  if (pollTimer != null) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

async function load(date = selectedDate.value) {
  loading.value = true
  error.value = ''
  try {
    stats.value = await api.statsToday(date)
    ranking.value = await api.ranking(date)
    if (stats.value.has_report) {
      report.value = await api.report(date)
    } else {
      report.value = null
    }
    if (stats.value.job_status === 'running' && !analyzing.value) {
      analyzing.value = true
      jobHint.value = '检测到进行中的分析任务…'
      schedulePoll(date)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    report.value = null
    ranking.value = []
  } finally {
    loading.value = false
  }
}

function applyDate(date: string) {
  const next = normalizeDate(date) || today
  const capped = next > today ? today : next
  stopPoll()
  analyzing.value = false
  analyzeMsg.value = ''
  jobHint.value = ''
  if (selectedDate.value !== capped) {
    selectedDate.value = capped
  }
  syncQuery(capped)
  return load(capped)
}

function onDatePicked() {
  applyDate(selectedDate.value)
}

function shiftDate(delta: number) {
  const next = shiftISO(selectedDate.value, delta)
  if (next > today) return
  applyDate(next)
}

function goToday() {
  applyDate(today)
}

async function loadLatestFallback() {
  try {
    report.value = await api.latestReport()
    if (report.value?.date) {
      selectedDate.value = report.value.date
      syncQuery(report.value.date)
      stats.value = await api.statsToday(report.value.date)
      ranking.value = await api.ranking(report.value.date)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function startAnalyze(force: boolean) {
  const date = selectedDate.value
  if (force) {
    const ok = window.confirm(
      `确定强制重跑 ${date} 的 AI 分析？将重新调用模型，不会跳过已有结果。`,
    )
    if (!ok) return
  }

  analyzing.value = true
  analyzeMsg.value = ''
  analyzeOk.value = false
  jobHint.value = force
    ? '已提交强制重跑任务…'
    : '已提交分析任务（已有结果将跳过）…'
  error.value = ''
  pollCount = 0
  stopPoll()

  try {
    const accepted = await api.triggerAnalyze(date, force)
    jobHint.value = accepted.message || '任务排队中…'
    if (accepted.status === 'success') {
      analyzing.value = false
      analyzeOk.value = true
      analyzeMsg.value = accepted.message || '分析完成'
      await load(date)
      return
    }
    schedulePoll(date)
  } catch (e) {
    analyzing.value = false
    analyzeOk.value = false
    analyzeMsg.value = e instanceof Error ? e.message : String(e)
  }
}

function schedulePoll(date: string) {
  stopPoll()
  pollTimer = setTimeout(() => void pollJob(date), POLL_MS)
}

async function pollJob(date: string) {
  if (date !== selectedDate.value) {
    analyzing.value = false
    return
  }
  pollCount += 1
  try {
    const jobs = await api.jobs(date)
    const latest = jobs[0]
    if (latest) {
      if (latest.status === 'running') {
        jobHint.value = latest.message || '分析进行中…'
      } else if (latest.status === 'success') {
        analyzing.value = false
        analyzeOk.value = true
        analyzeMsg.value = latest.message || '分析完成'
        jobHint.value = ''
        await load(date)
        return
      } else if (latest.status === 'failed') {
        analyzing.value = false
        analyzeOk.value = false
        analyzeMsg.value = latest.message || '分析失败'
        jobHint.value = ''
        stats.value = await api.statsToday(date)
        return
      }
    } else {
      const s = await api.statsToday(date)
      stats.value = s
      if (s.job_status === 'success' || s.has_report) {
        analyzing.value = false
        analyzeOk.value = true
        analyzeMsg.value = '分析完成'
        jobHint.value = ''
        await load(date)
        return
      }
      if (s.job_status === 'failed') {
        analyzing.value = false
        analyzeOk.value = false
        analyzeMsg.value = '分析失败'
        jobHint.value = ''
        return
      }
    }
  } catch (e) {
    jobHint.value = e instanceof Error ? e.message : '轮询任务状态失败，稍后重试…'
  }

  if (pollCount >= POLL_MAX) {
    analyzing.value = false
    analyzeOk.value = false
    analyzeMsg.value = '等待超时，请稍后刷新查看结果'
    jobHint.value = ''
    return
  }
  schedulePoll(date)
}

watch(
  () => route.query.date,
  (q) => {
    const fromRoute = normalizeDate(q) || today
    if (fromRoute !== selectedDate.value) {
      stopPoll()
      analyzing.value = false
      selectedDate.value = fromRoute
      load(fromRoute)
    }
  },
)

onMounted(() => load(selectedDate.value))
onUnmounted(stopPoll)
</script>
