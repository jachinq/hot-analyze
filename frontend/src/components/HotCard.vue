<template>
  <article class="hot-card">
    <div class="hot-card__meta">
      <span v-if="rank != null" class="hot-card__rank">#{{ rank }}</span>
      <span class="badge">{{ item.category || '其他' }}</span>
      <span class="source">{{ item.source || '未知来源' }}</span>
      <span class="heat">热度 {{ formatHeat(item.heat) }}</span>
    </div>
    <h3 class="hot-card__title">
      <a v-if="item.url" :href="item.url" target="_blank" rel="noopener">{{ item.title }}</a>
      <span v-else>{{ item.title }}</span>
    </h3>
    <p class="hot-card__summary">{{ item.summary || '暂无摘要' }}</p>
    <div class="hot-card__foot">
      <div class="stars" :title="`重要性 ${item.importance}/10`" :aria-label="`重要性 ${item.importance} 分`">
        <span v-for="i in 10" :key="i" :class="{ on: i <= item.importance }">★</span>
      </div>
      <div class="tags" v-if="item.tags?.length">
        <span v-for="t in item.tags.slice(0, 4)" :key="t" class="tag">{{ t }}</span>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { HotItem } from '../api'

withDefaults(
  defineProps<{ item: HotItem; rank?: number | null }>(),
  { rank: null },
)

function formatHeat(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return String(n ?? 0)
}
</script>
