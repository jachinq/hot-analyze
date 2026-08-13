import { computed, ref } from 'vue'

export type ThemeMode = 'system' | 'light' | 'dark'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'hot-analyze-theme'

const mode = ref<ThemeMode>('system')
const resolved = ref<ResolvedTheme>('light')
let initialized = false

function isThemeMode(value: unknown): value is ThemeMode {
  return value === 'system' || value === 'light' || value === 'dark'
}

function readStoredMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (isThemeMode(stored)) return stored
  } catch {
    /* ignore */
  }
  return 'system'
}

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function resolveTheme(next: ThemeMode): ResolvedTheme {
  return next === 'system' ? getSystemTheme() : next
}

function applyTheme(theme: ResolvedTheme) {
  const root = document.documentElement
  root.setAttribute('data-theme', theme)
  root.style.colorScheme = theme
}

function syncFromMode(next: ThemeMode) {
  mode.value = next
  resolved.value = resolveTheme(next)
  applyTheme(resolved.value)
}

export function setThemeMode(next: ThemeMode) {
  syncFromMode(next)
  try {
    localStorage.setItem(THEME_STORAGE_KEY, next)
  } catch {
    /* ignore */
  }
}

function initTheme() {
  if (initialized || typeof window === 'undefined') return
  initialized = true
  syncFromMode(readStoredMode())

  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  const onChange = () => {
    if (mode.value === 'system') {
      resolved.value = getSystemTheme()
      applyTheme(resolved.value)
    }
  }
  mq.addEventListener('change', onChange)
}

export function useTheme() {
  initTheme()
  return {
    mode,
    resolved,
    isDark: computed(() => resolved.value === 'dark'),
    setMode: setThemeMode,
  }
}
