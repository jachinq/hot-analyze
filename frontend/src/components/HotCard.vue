<template>
  <article class="hot-card">
    <div class="hot-card__meta">
      <span v-if="rank != null" class="hot-card__rank">#{{ rank }}</span>
      <span class="badge">{{ item.category || '其他' }}</span>
      <span class="source">{{ sourceLabel }}</span>
      <span class="hot-card__stat heat">热度 {{ formatHeat(item.heat) }}</span>
      <span class="hot-card__stat" title="AI/规则原始分数">原始 {{ item.raw_importance ?? item.importance }}</span>
      <span
        v-if="item.rank != null"
        class="hot-card__stat"
        title="采集榜内名次，越小越热"
      >排名 {{ item.rank }}</span>
      <span
        v-if="(item.category_boost ?? 0) !== 0"
        class="hot-card__stat"
        title="分类偏好加减分（关心+/忽略-）；忽略类话题整体靠后"
      >分类 {{ formatBoost(item.category_boost) }}</span>
    </div>
    <h3 class="hot-card__title">
      <a v-if="item.url" :href="item.url" target="_blank" rel="noopener">{{ item.title }}</a>
      <span v-else>{{ item.title }}</span>
    </h3>
    <p class="hot-card__summary">{{ item.summary || '暂无摘要' }}</p>
    <div class="hot-card__foot">
      <div
        class="stars"
        :title="`有效重要性 ${item.importance}/10（原始 ${item.raw_importance ?? '—'} + 分类 ${formatBoost(item.category_boost)}）`"
        :aria-label="`有效重要性 ${item.importance} 分`"
      >
        <span v-for="i in 10" :key="i" :class="{ on: i <= item.importance }">★</span>
      </div>
      <div class="tags" v-if="item.tags?.length">
        <span v-for="t in item.tags.slice(0, 4)" :key="t" class="tag">{{ t }}</span>
      </div>
    </div>

    <div v-if="memberCount > 1" class="hot-card__members">
      <button
        type="button"
        class="hot-card__toggle"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        <span class="hot-card__toggle-icon" :class="{ open: expanded }" aria-hidden="true">▸</span>
        同话题 {{ memberCount }} 条
      </button>
      <ul v-if="expanded" class="hot-card__member-list">
        <li v-for="m in item.members" :key="m.hot_id" class="hot-card__member">
          <a
            v-if="m.url"
            :href="m.url"
            target="_blank"
            rel="noopener"
            class="hot-card__member-title"
          >{{ m.title }}</a>
          <span v-else class="hot-card__member-title">{{ m.title }}</span>
          <span class="hot-card__member-meta">
            <span>{{ m.source || '未知' }}</span>
            <span>{{ formatHeat(m.heat) }}</span>
            <span v-if="m.rank != null">排名 {{ m.rank }}</span>
          </span>
        </li>
      </ul>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TopicItem } from '../api'

const props = withDefaults(
  defineProps<{ item: TopicItem; rank?: number | null }>(),
  { rank: null },
)

const expanded = ref(false)

const memberCount = computed(
  () => props.item.member_count ?? props.item.members?.length ?? 1,
)

const sourceLabel = computed(() => {
  const sources = props.item.sources?.filter(Boolean) || []
  if (sources.length > 1) return `${sources[0]} 等${sources.length}源`
  return props.item.source || sources[0] || '未知来源'
})

function formatHeat(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return String(n ?? 0)
}

function formatBoost(n?: number | null) {
  const v = n ?? 0
  if (v > 0) return `+${v}`
  return String(v)
}
</script>
