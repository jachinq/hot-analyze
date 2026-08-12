<template>
  <div class="page">
    <section class="hero-panel compact">
      <div>
        <p class="eyebrow">系统设置</p>
        <h1>上游服务 / AI / 调度 / 流水线</h1>
        <p class="lead">配置写入数据库，保存后立即生效；YAML 仅作首次种子与兜底。</p>
      </div>
    </section>

    <p v-if="loadError" class="error">{{ loadError }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <template v-if="settings && !loading">
      <!-- Collector -->
      <section class="panel settings-section">
        <div class="settings-head">
          <h2>上游 Collector</h2>
          <div class="settings-actions">
            <button
              type="button"
              class="ghost"
              :disabled="testing === 'collector' || saving === 'collector'"
              @click="testCollector"
            >
              {{ testing === 'collector' ? '测试中…' : '测试连接' }}
            </button>
            <button type="button" :disabled="saving === 'collector'" @click="saveCollector">
              {{ saving === 'collector' ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
        <p
          v-if="msg.collector"
          class="hint"
          :class="{ ok: testOk.collector === true, bad: testOk.collector === false }"
        >
          {{ msg.collector }}
        </p>
        <div class="form-grid">
          <label>
            Base URL
            <input v-model="settings.collector.base_url" type="url" />
          </label>
          <label>
            List Path
            <input v-model="settings.collector.list_path" type="text" />
          </label>
          <label>
            超时（秒）
            <input v-model.number="settings.collector.timeout_sec" type="number" min="1" />
          </label>
          <label>
            最大重试
            <input v-model.number="settings.collector.max_retries" type="number" min="0" />
          </label>
        </div>
      </section>

      <!-- AI globals -->
      <section class="panel settings-section">
        <div class="settings-head">
          <h2>AI 全局参数</h2>
          <button type="button" :disabled="saving === 'ai'" @click="saveAi">
            {{ saving === 'ai' ? '保存中…' : '保存' }}
          </button>
        </div>
        <p v-if="msg.ai" class="hint" :class="{ ok: !msg.ai.startsWith('失败') }">{{ msg.ai }}</p>
        <div class="form-grid">
          <label class="checkbox">
            <input v-model="settings.ai.prefer_local" type="checkbox" />
            优先本地模型
          </label>
          <label>
            默认 Provider
            <input v-model="settings.ai.default_provider" type="text" />
          </label>
          <label>
            日调用上限
            <input v-model.number="settings.ai.max_calls_per_day" type="number" min="1" />
          </label>
          <label>
            日 Token 上限
            <input v-model.number="settings.ai.max_tokens_per_day" type="number" min="1" />
          </label>
          <label>
            超时（秒）
            <input v-model.number="settings.ai.timeout_sec" type="number" min="1" step="1" />
          </label>
        </div>
      </section>

      <!-- AI providers -->
      <section class="panel settings-section">
        <div class="settings-head">
          <h2>AI Provider</h2>
          <button type="button" class="ghost" :disabled="providersLoading" @click="loadProviders">
            刷新
          </button>
        </div>
        <p v-if="msg.providers" class="hint" :class="{ ok: !msg.providers.startsWith('失败') }">
          {{ msg.providers }}
        </p>
        <p v-if="providersLoading" class="muted">加载 Provider…</p>
        <div v-for="p in providers" :key="p.id" class="provider-card">
          <div class="provider-title">
            <strong>{{ p.name }}</strong>
            <span class="muted">{{ p.provider }}</span>
            <label class="checkbox inline">
              <input v-model="p.enabled" type="checkbox" />
              启用
            </label>
          </div>
          <div class="form-grid">
            <label>
              模型
              <input v-model="p.model" type="text" />
            </label>
            <label>
              API URL
              <input v-model="p.api_url" type="url" />
            </label>
            <label>
              优先级
              <input v-model.number="p.priority" type="number" />
            </label>
            <label>
              API Key（留空或 **** 表示不改）
              <input v-model="p.api_key" type="password" autocomplete="off" />
            </label>
          </div>
          <p
            v-if="providerMsg[p.id]"
            class="hint"
            :class="{
              ok: providerTestOk[p.id] === true,
              bad: providerTestOk[p.id] === false,
            }"
          >
            {{ providerMsg[p.id] }}
          </p>
          <div class="settings-actions">
            <button
              type="button"
              class="ghost"
              :disabled="testing === `provider-${p.id}` || saving === `provider-${p.id}`"
              @click="testProvider(p)"
            >
              {{ testing === `provider-${p.id}` ? '测试中…' : '测试连接' }}
            </button>
            <button
              type="button"
              :disabled="saving === `provider-${p.id}`"
              @click="saveProvider(p)"
            >
              {{ saving === `provider-${p.id}` ? '保存中…' : '保存此 Provider' }}
            </button>
          </div>
        </div>
        <p v-if="!providersLoading && !providers.length" class="muted">暂无 Provider 配置</p>
      </section>

      <!-- Scheduler -->
      <section class="panel settings-section">
        <div class="settings-head">
          <h2>调度</h2>
          <button type="button" :disabled="saving === 'scheduler'" @click="saveScheduler">
            {{ saving === 'scheduler' ? '保存中…' : '保存' }}
          </button>
        </div>
        <p v-if="msg.scheduler" class="hint" :class="{ ok: !msg.scheduler.startsWith('失败') }">
          {{ msg.scheduler }}
        </p>
        <div class="form-grid">
          <label class="checkbox">
            <input v-model="settings.scheduler.enabled" type="checkbox" />
            启用定时任务
          </label>
          <label>
            Cron（分 时 日 月 周）
            <input v-model="settings.scheduler.daily_cron" type="text" placeholder="0 8 * * *" />
          </label>
          <label>
            时区
            <input v-model="settings.scheduler.timezone" type="text" />
          </label>
        </div>
      </section>

      <!-- Pipeline -->
      <section class="panel settings-section">
        <div class="settings-head">
          <h2>流水线</h2>
          <button type="button" :disabled="saving === 'pipeline'" @click="savePipeline">
            {{ saving === 'pipeline' ? '保存中…' : '保存' }}
          </button>
        </div>
        <p v-if="msg.pipeline" class="hint" :class="{ ok: !msg.pipeline.startsWith('失败') }">
          {{ msg.pipeline }}
        </p>
        <h3 class="subhead">聚类</h3>
        <div class="form-grid">
          <label class="checkbox">
            <input v-model="settings.pipeline.cluster.enabled" type="checkbox" />
            启用聚类
          </label>
          <label>
            方法
            <select v-model="settings.pipeline.cluster.method">
              <option value="tfidf">tfidf</option>
              <option value="title_sim">title_sim</option>
            </select>
          </label>
          <label>
            相似度阈值
            <input
              v-model.number="settings.pipeline.cluster.similarity_threshold"
              type="number"
              min="0"
              max="1"
              step="0.01"
            />
          </label>
        </div>
        <h3 class="subhead">分类</h3>
        <div class="form-grid">
          <label class="checkbox">
            <input v-model="settings.pipeline.classify.rule_first" type="checkbox" />
            规则优先
          </label>
          <label class="checkbox">
            <input v-model="settings.pipeline.classify.ai_fallback" type="checkbox" />
            AI 回退
          </label>
          <label>
            批大小
            <input v-model.number="settings.pipeline.batch_size" type="number" min="1" />
          </label>
          <label>
            日报 Top N
            <input v-model.number="settings.pipeline.report_top_n" type="number" min="1" />
          </label>
        </div>
        <h3 class="subhead">分类偏好（逗号分隔，越前权重越大）</h3>
        <div class="form-grid">
          <label class="grow">
            关心（care）
            <input v-model="careText" type="text" placeholder="社会, 科技, 财经" />
          </label>
          <label class="grow">
            忽略（ignore）
            <input v-model="ignoreText" type="text" placeholder="娱乐, 体育" />
          </label>
          <label>
            boost_max
            <input
              v-model.number="settings.pipeline.category_preference.boost_max"
              type="number"
              min="0"
            />
          </label>
          <label>
            suppress_max
            <input
              v-model.number="settings.pipeline.category_preference.suppress_max"
              type="number"
              min="0"
            />
          </label>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  api,
  type AIProviderConfig,
  type SystemSettings,
} from '../api'

const settings = ref<SystemSettings | null>(null)
const providers = ref<AIProviderConfig[]>([])
const loading = ref(true)
const providersLoading = ref(false)
const loadError = ref('')
const saving = ref('')
const testing = ref('')
const msg = reactive<Record<string, string>>({
  collector: '',
  ai: '',
  providers: '',
  scheduler: '',
  pipeline: '',
})
const testOk = reactive<Record<string, boolean | null>>({
  collector: null,
})
const providerMsg = reactive<Record<number, string>>({})
const providerTestOk = reactive<Record<number, boolean | null>>({})

const careText = ref('')
const ignoreText = ref('')

function splitList(text: string): string[] {
  return text
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function formatTestMsg(ok: boolean, message: string, latencyMs?: number | null) {
  const latency =
    latencyMs != null && Number.isFinite(latencyMs) ? `（${Math.round(latencyMs)} ms）` : ''
  return `${ok ? '✓' : '✗'} ${message}${latency}`
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    settings.value = await api.getSettings()
    careText.value = settings.value.pipeline.category_preference.care.join(', ')
    ignoreText.value = settings.value.pipeline.category_preference.ignore.join(', ')
    await loadProviders()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function loadProviders() {
  providersLoading.value = true
  try {
    providers.value = await api.listAiConfig()
  } catch (e) {
    msg.providers = `失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    providersLoading.value = false
  }
}

async function testCollector() {
  if (!settings.value) return
  testing.value = 'collector'
  msg.collector = ''
  testOk.collector = null
  try {
    const result = await api.testCollector(settings.value.collector)
    testOk.collector = result.ok
    msg.collector = formatTestMsg(result.ok, result.message, result.latency_ms)
  } catch (e) {
    testOk.collector = false
    msg.collector = formatTestMsg(false, e instanceof Error ? e.message : String(e))
  } finally {
    testing.value = ''
  }
}

async function testProvider(p: AIProviderConfig) {
  testing.value = `provider-${p.id}`
  providerMsg[p.id] = ''
  providerTestOk[p.id] = null
  try {
    const body: {
      id: number
      name: string
      provider: string
      api_url: string
      model: string
      api_key?: string
      timeout_sec?: number
    } = {
      id: p.id,
      name: p.name,
      provider: p.provider,
      api_url: p.api_url || '',
      model: p.model,
      timeout_sec: settings.value?.ai.timeout_sec,
    }
    if (p.api_key && p.api_key !== '****') {
      body.api_key = p.api_key
    }
    const result = await api.testAiProvider(body)
    providerTestOk[p.id] = result.ok
    providerMsg[p.id] = formatTestMsg(result.ok, result.message, result.latency_ms)
  } catch (e) {
    providerTestOk[p.id] = false
    providerMsg[p.id] = formatTestMsg(false, e instanceof Error ? e.message : String(e))
  } finally {
    testing.value = ''
  }
}

async function saveCollector() {
  if (!settings.value) return
  saving.value = 'collector'
  msg.collector = ''
  testOk.collector = null
  try {
    settings.value = await api.updateSettings({ collector: settings.value.collector })
    msg.collector = '已保存'
  } catch (e) {
    testOk.collector = false
    msg.collector = `失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    saving.value = ''
  }
}

async function saveAi() {
  if (!settings.value) return
  saving.value = 'ai'
  msg.ai = ''
  try {
    settings.value = await api.updateSettings({ ai: settings.value.ai })
    msg.ai = '已保存'
  } catch (e) {
    msg.ai = `失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    saving.value = ''
  }
}

async function saveScheduler() {
  if (!settings.value) return
  saving.value = 'scheduler'
  msg.scheduler = ''
  try {
    settings.value = await api.updateSettings({ scheduler: settings.value.scheduler })
    msg.scheduler = '已保存（调度已热更新）'
  } catch (e) {
    msg.scheduler = `失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    saving.value = ''
  }
}

async function savePipeline() {
  if (!settings.value) return
  saving.value = 'pipeline'
  msg.pipeline = ''
  try {
    settings.value.pipeline.category_preference.care = splitList(careText.value)
    settings.value.pipeline.category_preference.ignore = splitList(ignoreText.value)
    settings.value = await api.updateSettings({ pipeline: settings.value.pipeline })
    careText.value = settings.value.pipeline.category_preference.care.join(', ')
    ignoreText.value = settings.value.pipeline.category_preference.ignore.join(', ')
    msg.pipeline = '已保存'
  } catch (e) {
    msg.pipeline = `失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    saving.value = ''
  }
}

async function saveProvider(p: AIProviderConfig) {
  saving.value = `provider-${p.id}`
  msg.providers = ''
  try {
    const body: {
      model: string
      api_url?: string
      enabled: boolean
      priority: number
      api_key?: string
    } = {
      model: p.model,
      api_url: p.api_url || undefined,
      enabled: p.enabled,
      priority: p.priority,
    }
    if (p.api_key && p.api_key !== '****') {
      body.api_key = p.api_key
    }
    const updated = await api.updateAiConfig(p.id, body)
    const idx = providers.value.findIndex((x) => x.id === p.id)
    if (idx >= 0) providers.value[idx] = updated
    msg.providers = `已保存 ${updated.name}`
  } catch (e) {
    msg.providers = `失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    saving.value = ''
  }
}

onMounted(loadAll)
</script>
