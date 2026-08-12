export interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

export interface HotItem {
  hot_id: number
  title: string
  category?: string | null
  sub_category?: string | null
  summary?: string | null
  importance: number
  tags: string[]
  source?: string | null
  heat: number
  url?: string | null
  cluster_id?: string | null
}

export interface TopicMember {
  hot_id: number
  title: string
  source?: string | null
  heat: number
  url?: string | null
}

/** 话题卡：代表条 + 可展开成员；heat 为成员 max(heat) */
export interface TopicItem extends HotItem {
  member_count: number
  sources: string[]
  members: TopicMember[]
}

export interface ReportContent {
  highlights?: Array<{ title?: string; impact?: number; summary?: string; url?: string }>
  trends?: string[]
  markdown?: string
}

export interface Report {
  date: string
  summary?: string | null
  hot_count: number
  topic_count?: number
  content?: ReportContent | null
  items: TopicItem[]
}

export interface CategoryStat {
  category: string
  count: number
}

export interface TodayStats {
  date: string
  hot_count: number
  topic_count?: number
  categories: CategoryStat[]
  has_report: boolean
  report_summary?: string | null
  job_status?: string | null
}

export interface JobRun {
  id: number
  job_name: string
  report_date?: string | null
  status: string
  message?: string | null
  progress?: number
  stage?: string | null
  current?: number
  total?: number
  started_at?: string | null
  finished_at?: string | null
}

export interface AnalyzeAccepted {
  date: string
  status: string
  message?: string
  job_id?: number
  hot_count?: number
  progress?: number
  stage?: string
  ai_calls?: number
  skipped?: number
  reused?: number
}

export interface AIGlobals {
  prefer_local: boolean
  max_calls_per_day: number
  max_tokens_per_day: number
  timeout_sec: number
  default_provider: string
}

export interface CollectorSettings {
  base_url: string
  list_path: string
  timeout_sec: number
  max_retries: number
}

export interface SchedulerSettings {
  daily_cron: string
  timezone: string
  enabled: boolean
}

export interface PipelineSettings {
  cluster: {
    enabled: boolean
    method: string
    similarity_threshold: number
  }
  classify: {
    rule_first: boolean
    ai_fallback: boolean
  }
  category_preference: {
    care: string[]
    ignore: string[]
    boost_max: number
    suppress_max: number
  }
  batch_size: number
  report_top_n: number
}

export interface SystemSettings {
  collector: CollectorSettings
  ai: AIGlobals
  scheduler: SchedulerSettings
  pipeline: PipelineSettings
}

export interface AIProviderConfig {
  id: number
  name: string
  provider: string
  model: string
  api_url?: string | null
  api_key: string
  enabled: boolean
  priority: number
  updated_at?: string | null
}

export type AIProviderUpdate = {
  model?: string
  api_url?: string
  api_key?: string
  enabled?: boolean
  priority?: number
}

export interface ConnectionTestResult {
  ok: boolean
  message: string
  latency_ms?: number | null
  detail?: Record<string, unknown> | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { Accept: 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  const body = (await res.json()) as ApiResponse<T>
  if (body.code !== 0 && body.code !== undefined) {
    throw new Error(body.message || 'request failed')
  }
  return body.data
}

export function todayISO() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export const api = {
  statsToday: (date?: string) =>
    request<TodayStats>(`/api/stats/today${date ? `?date=${date}` : ''}`),
  report: (date: string) => request<Report>(`/api/report/${date}`),
  latestReport: () => request<Report>('/api/report/latest'),
  ranking: (date?: string, by: 'importance' | 'heat' = 'importance') =>
    request<TopicItem[]>(
      `/api/hot/ranking?by=${by}${date ? `&date=${date}` : ''}`,
    ),
  byCategory: (category: string, date?: string) =>
    request<TopicItem[]>(
      `/api/hot/category?category=${encodeURIComponent(category)}${date ? `&date=${date}` : ''}`,
    ),
  search: (params: { date?: string; category?: string; keyword?: string }) => {
    const q = new URLSearchParams()
    if (params.date) q.set('date', params.date)
    if (params.category) q.set('category', params.category)
    if (params.keyword) q.set('keyword', params.keyword)
    return request<TopicItem[]>(`/api/hot/search?${q.toString()}`)
  },
  /** 手动触发分析；force=false 时跳过已有 AI 结果 */
  triggerAnalyze: (date: string, force = false) => {
    const q = new URLSearchParams({ date, force: String(force) })
    return request<AnalyzeAccepted>(`/api/jobs/analyze?${q.toString()}`, {
      method: 'POST',
    })
  },
  jobs: (date: string) => request<JobRun[]>(`/api/jobs/${date}`),
  getSettings: () => request<SystemSettings>('/api/settings'),
  updateSettings: (body: Partial<SystemSettings>) =>
    request<SystemSettings>('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  listAiConfig: () => request<AIProviderConfig[]>('/api/ai/config'),
  updateAiConfig: (id: number, body: AIProviderUpdate) =>
    request<AIProviderConfig>(`/api/ai/config/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  testCollector: (body: CollectorSettings) =>
    request<ConnectionTestResult>('/api/settings/test/collector', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  testAiProvider: (body: {
    id?: number
    name?: string
    provider: string
    api_url: string
    model: string
    api_key?: string
    timeout_sec?: number
  }) =>
    request<ConnectionTestResult>('/api/settings/test/ai-provider', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
