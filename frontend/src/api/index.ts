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

export interface ReportContent {
  highlights?: Array<{ title?: string; impact?: number; summary?: string }>
  trends?: string[]
  markdown?: string
}

export interface Report {
  date: string
  summary?: string | null
  hot_count: number
  content?: ReportContent | null
  items: HotItem[]
}

export interface CategoryStat {
  category: string
  count: number
}

export interface TodayStats {
  date: string
  hot_count: number
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
  started_at?: string | null
  finished_at?: string | null
}

export interface AnalyzeAccepted {
  date: string
  status: string
  message?: string
  job_id?: number
  hot_count?: number
  ai_calls?: number
  skipped?: number
  reused?: number
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
    request<HotItem[]>(
      `/api/hot/ranking?by=${by}${date ? `&date=${date}` : ''}`,
    ),
  byCategory: (category: string, date?: string) =>
    request<HotItem[]>(
      `/api/hot/category?category=${encodeURIComponent(category)}${date ? `&date=${date}` : ''}`,
    ),
  search: (params: { date?: string; category?: string; keyword?: string }) => {
    const q = new URLSearchParams()
    if (params.date) q.set('date', params.date)
    if (params.category) q.set('category', params.category)
    if (params.keyword) q.set('keyword', params.keyword)
    return request<HotItem[]>(`/api/hot/search?${q.toString()}`)
  },
  /** 手动触发分析；force=false 时跳过已有 AI 结果 */
  triggerAnalyze: (date: string, force = false) => {
    const q = new URLSearchParams({ date, force: String(force) })
    return request<AnalyzeAccepted>(`/api/jobs/analyze?${q.toString()}`, {
      method: 'POST',
    })
  },
  jobs: (date: string) => request<JobRun[]>(`/api/jobs/${date}`),
}
