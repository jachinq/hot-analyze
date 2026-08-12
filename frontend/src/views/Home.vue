<template>
  <div class="page">
    <section class="hero-panel">
      <div class="hero-copy">
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
          <p class="analyze-hint" v-if="!analyzing">
            <template v-if="stats?.has_report">
              该日已有分析，再次运行会跳过已总结条目，仅补全新增热点并刷新日报
            </template>
            <template v-else>
              按当前日期触发 AI 总结；已有条目会自动跳过
            </template>
          </p>
        </div>

        <div v-if="analyzing" class="job-progress">
          <div class="job-progress__meta">
            <span class="job-progress__stage">{{ stageLabel }}</span>
            <span class="job-progress__pct">{{ displayProgress }}%</span>
          </div>
          <div
            class="job-progress__track"
            role="progressbar"
            :aria-valuenow="displayProgress"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <div
              class="job-progress__fill"
              :class="{ indeterminate: jobProgress <= 0 }"
              :style="{ width: jobProgress <= 0 ? '28%' : `${displayProgress}%` }"
            />
          </div>
          <p class="job-progress__detail">
            <template v-if="jobTotal > 0">{{ jobCurrent }}/{{ jobTotal }} · </template>
            {{ jobHint || '任务进行中…' }}
          </p>
        </div>

        <p v-if="analyzeMsg && !analyzing" class="hint" :class="{ ok: analyzeOk }">{{ analyzeMsg }}</p>
        <p v-if="stats && !stats.has_report && !analyzing" class="hint">
          任务状态：{{ stats.job_status || '未运行' }}
          <button class="linkish" @click="loadLatestFallback">查看最近日报</button>
        </p>
      </div>
      <div class="stat-block" aria-label="当日概览指标">
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

    <section class="panel" v-if="!loading && report?.content?.markdown">
      <h2>AI 日报</h2>
      <div class="markdown" v-html="markdownHtml"></div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading" class="muted">加载中…</p>

    <section class="grid" v-if="stats && !loading">
      <div class="panel">
        <h2>分类分布</h2>
        <div class="bars" v-if="stats.categories.length">
          <div v-for="(c, idx) in stats.categories" :key="c.category" class="bar-row">
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
              <div
                class="bar-fill"
                :style="{
                  width: barWidth(c.count),
                  animationDelay: `${Math.min(idx, 8) * 0.05}s`,
                }"
              ></div>
            </div>
            <span class="bar-count">{{ c.count }}</span>
          </div>
        </div>
        <p v-else class="muted">暂无分类数据</p>
      </div>

      <!-- <div class="panel">
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
      </div> -->
    </section>

    <!-- <section class="panel" v-if="!loading && report?.content?.highlights?.length">
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
    </section> -->

    <section class="panel" v-if="!loading && report?.items?.length">
      <h2>热点列表</h2>
      <div class="card-list">
        <HotCard
          v-for="(item, idx) in report.items"
          :key="item.hot_id"
          :item="item"
          :rank="idx + 1"
          :style="{ animationDelay: `${Math.min(idx, 12) * 0.04}s` }"
          class="hot-card--stagger"
        />
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

const POLL_MS = 1200
const POLL_MAX = 250

const STAGE_LABELS: Record<string, string> = {
  fetch: '拉取热点',
  cluster: '聚类去重',
  analyze: 'AI 分析',
  report: '生成日报',
  done: '已完成',
  failed: '失败',
}

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
const jobProgress = ref(0)
const jobStage = ref('')
const jobCurrent = ref(0)
const jobTotal = ref(0)
const stats = ref<TodayStats | null>(null)
const report = ref<Report | null>(null)
const ranking = ref<HotItem[]>([])

let pollTimer: ReturnType<typeof setTimeout> | null = null
let pollCount = 0

const isToday = computed(() => selectedDate.value === today)
const displayProgress = computed(() => Math.max(0, Math.min(100, jobProgress.value)))
const stageLabel = computed(
  () => STAGE_LABELS[jobStage.value] || (analyzing.value ? '排队中' : '进度'),
)

const maxCat = computed(() =>
  Math.max(1, ...(stats.value?.categories.map((c) => c.count) || [1])),
)

function barWidth(count: number) {
  return `${Math.round((count / maxCat.value) * 100)}%`
}

const markdownHtml = computed(() => {
  const md = report.value?.content?.markdown || ''
  const html = marked.parse(md, { async: false }) as string
  return linkifyHighlightTitles(html, report.value?.items || [])
})

/** 将「重点事件」里的标题匹配热点 URL，包成可点击链接 */
function linkifyHighlightTitles(html: string, items: HotItem[]): string {
  const linked = items.filter((i) => i.url && i.title?.trim())
  if (!html || !linked.length) return html

  const byNorm = new Map<string, string>()
  for (const it of linked) {
    byNorm.set(normalizeTitle(it.title), it.url!)
  }

  const findUrl = (raw: string): string | null => {
    const t = normalizeTitle(raw)
    if (!t) return null
    const exact = byNorm.get(t)
    if (exact) return exact
    // AI 可能微调标题：用最长包含匹配
    let best: { url: string; len: number } | null = null
    for (const it of linked) {
      const nt = normalizeTitle(it.title)
      if (!nt) continue
      if (t.includes(nt) || nt.includes(t)) {
        if (!best || nt.length > best.len) best = { url: it.url!, len: nt.length }
      }
    }
    return best?.url ?? null
  }

  if (typeof DOMParser === 'undefined') return html
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const body = doc.body

  const headings = Array.from(body.querySelectorAll('h1, h2, h3, h4'))
  const start = headings.find((h) => (h.textContent || '').includes('重点事件'))
  const scopeRoots: Element[] = []
  if (start) {
    let node: ChildNode | null = start.nextSibling
    while (node) {
      if (node instanceof HTMLElement && /^H[1-4]$/i.test(node.tagName)) break
      if (node instanceof HTMLElement) scopeRoots.push(node)
      node = node.nextSibling
    }
  } else {
    scopeRoots.push(body)
  }

  for (const root of scopeRoots) {
    for (const strong of Array.from(root.querySelectorAll('strong, b'))) {
      if (strong.closest('a')) continue
      if (strong.querySelector('a')) continue
      const url = findUrl(strong.textContent || '')
      if (!url) continue
      const a = doc.createElement('a')
      a.href = url
      a.target = '_blank'
      a.rel = 'noopener noreferrer'
      a.className = 'md-hot-link'
      while (strong.firstChild) a.appendChild(strong.firstChild)
      strong.appendChild(a)
    }

    for (const li of Array.from(root.querySelectorAll('li'))) {
      if (li.querySelector('a')) continue
      const text = (li.textContent || '').trim()
      if (!text) continue
      let best: { title: string; url: string; len: number } | null = null
      for (const it of linked) {
        const title = it.title.trim()
        const nt = normalizeTitle(title)
        if (!nt || nt.length < 4) continue
        if (normalizeTitle(text).startsWith(nt) || text.startsWith(title)) {
          if (!best || nt.length > best.len) best = { title, url: it.url!, len: nt.length }
        }
      }
      if (!best) continue

      const walker = doc.createTreeWalker(li, NodeFilter.SHOW_TEXT)
      let textNode: Text | null = null
      while (walker.nextNode()) {
        const n = walker.currentNode as Text
        if ((n.nodeValue || '').includes(best.title)) {
          textNode = n
          break
        }
      }
      if (!textNode?.nodeValue || !textNode.parentNode) continue
      const full = textNode.nodeValue
      const at = full.indexOf(best.title)
      if (at < 0) continue
      const before = full.slice(0, at)
      const after = full.slice(at + best.title.length)
      const a = doc.createElement('a')
      a.href = best.url
      a.target = '_blank'
      a.rel = 'noopener noreferrer'
      a.className = 'md-hot-link'
      a.textContent = best.title
      const parent = textNode.parentNode
      if (before) parent.insertBefore(doc.createTextNode(before), textNode)
      parent.insertBefore(a, textNode)
      if (after) parent.insertBefore(doc.createTextNode(after), textNode)
      parent.removeChild(textNode)
    }
  }

  return body.innerHTML
}

function normalizeTitle(s: string | null | undefined): string {
  return (s || '').replace(/\s+/g, '').trim()
}

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

function resetProgress() {
  jobProgress.value = 0
  jobStage.value = ''
  jobCurrent.value = 0
  jobTotal.value = 0
  jobHint.value = ''
}

function applyJobProgress(job: {
  progress?: number | null
  stage?: string | null
  current?: number | null
  total?: number | null
  message?: string | null
}) {
  if (typeof job.progress === 'number') jobProgress.value = job.progress
  if (job.stage) jobStage.value = job.stage
  if (typeof job.current === 'number') jobCurrent.value = job.current
  if (typeof job.total === 'number') jobTotal.value = job.total
  if (job.message) jobHint.value = job.message
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
      try {
        const jobs = await api.jobs(date)
        if (jobs[0]) applyJobProgress(jobs[0])
      } catch {
        /* ignore */
      }
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
  resetProgress()
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
  resetProgress()
  jobStage.value = 'fetch'
  jobHint.value = force
    ? '已提交强制重跑任务…'
    : '已提交分析任务（已有结果将跳过）…'
  error.value = ''
  pollCount = 0
  stopPoll()

  try {
    const accepted = await api.triggerAnalyze(date, force)
    applyJobProgress(accepted)
    jobHint.value = accepted.message || '任务排队中…'
    if (accepted.status === 'success') {
      jobProgress.value = 100
      jobStage.value = 'done'
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
      applyJobProgress(latest)
      if (latest.status === 'running') {
        // keep polling
      } else if (latest.status === 'success') {
        jobProgress.value = 100
        jobStage.value = 'done'
        analyzing.value = false
        analyzeOk.value = true
        analyzeMsg.value = latest.message || '分析完成'
        await load(date)
        return
      } else if (latest.status === 'failed') {
        jobStage.value = 'failed'
        analyzing.value = false
        analyzeOk.value = false
        analyzeMsg.value = latest.message || '分析失败'
        stats.value = await api.statsToday(date)
        return
      }
    } else {
      const s = await api.statsToday(date)
      stats.value = s
      if (s.job_status === 'success' || s.has_report) {
        jobProgress.value = 100
        jobStage.value = 'done'
        analyzing.value = false
        analyzeOk.value = true
        analyzeMsg.value = '分析完成'
        await load(date)
        return
      }
      if (s.job_status === 'failed') {
        jobStage.value = 'failed'
        analyzing.value = false
        analyzeOk.value = false
        analyzeMsg.value = '分析失败'
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
      analyzeMsg.value = ''
      resetProgress()
      selectedDate.value = fromRoute
      load(fromRoute)
    }
  },
)

onMounted(() => load(selectedDate.value))
onUnmounted(stopPoll)
</script>
