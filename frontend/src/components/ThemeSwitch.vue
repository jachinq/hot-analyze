<template>
  <div class="theme-switch" role="radiogroup" aria-label="主题">
    <button
      v-for="opt in options"
      :key="opt.id"
      type="button"
      class="theme-switch__btn"
      role="radio"
      :aria-checked="mode === opt.id"
      :aria-label="opt.label"
      :title="opt.label"
      :class="{ active: mode === opt.id }"
      @click="setMode(opt.id)"
    >
      <svg
        class="theme-switch__icon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <template v-if="opt.id === 'system'">
          <rect x="3.5" y="4.5" width="17" height="12" rx="1.8" />
          <path d="M8 19.5h8M12 16.5v3" />
        </template>
        <template v-else-if="opt.id === 'light'">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 3.2v1.6M12 19.2v1.6M4.8 12H3.2M20.8 12h-1.6M6.2 6.2l1.1 1.1M16.7 16.7l1.1 1.1M17.8 6.2l-1.1 1.1M7.3 16.7l-1.1 1.1" />
        </template>
        <template v-else>
          <path d="M15.2 4.3a7.4 7.4 0 1 0 4.5 13.1 6.2 6.2 0 0 1-4.5-13.1z" />
        </template>
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { useTheme, type ThemeMode } from '../composables/useTheme'

const { mode, setMode } = useTheme()

const options: { id: ThemeMode; label: string }[] = [
  { id: 'system', label: '跟随系统' },
  { id: 'light', label: '明亮主题' },
  { id: 'dark', label: '黑暗主题' },
]
</script>

<style scoped>
.theme-switch {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
  flex-shrink: 0;
}

.theme-switch__btn {
  width: 2rem;
  height: 2rem;
  padding: 0;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  filter: none !important;
  transform: none !important;
  transition: color 0.2s ease, background 0.2s ease;
}

.theme-switch__btn:hover {
  color: var(--ink);
  background: var(--nav-hover-bg);
  filter: none;
}

.theme-switch__btn.active {
  color: var(--accent-deep);
  background: var(--accent-soft);
}

.theme-switch__icon {
  width: 1.05rem;
  height: 1.05rem;
}
</style>
