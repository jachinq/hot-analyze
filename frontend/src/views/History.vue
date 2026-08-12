<template>
  <div class="page">
    <section class="hero-panel compact">
      <div class="hero-copy">
        <p class="eyebrow">历史检索</p>
        <h1>按日期 / 分类 / 关键词查找</h1>
      </div>
    </section>

    <form class="search-bar panel" @submit.prevent="load">
      <label>
        日期
        <input type="date" v-model="form.date" />
      </label>
      <label>
        分类
        <select v-model="form.category">
          <option value="">全部</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
      </label>
      <label class="grow">
        关键词
        <input type="search" v-model="form.keyword" placeholder="标题 / 摘要 / 标签" />
      </label>
      <button type="submit">搜索</button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="muted">搜索中…</p>

    <div class="card-grid" v-if="items.length">
      <HotCard v-for="item in items" :key="`${item.hot_id}-${item.title}`" :item="item" />
    </div>
    <p v-else-if="searched && !loading" class="muted">无匹配结果</p>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { api, todayISO, type HotItem } from '../api'
import HotCard from '../components/HotCard.vue'

const categories = ['科技', '财经', '新闻', '社会', '娱乐', '体育', '军事', '其他']
const form = reactive({
  date: todayISO(),
  category: '',
  keyword: '',
})
const items = ref<HotItem[]>([])
const loading = ref(false)
const searched = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  searched.value = true
  error.value = ''
  try {
    items.value = await api.search({
      date: form.date || undefined,
      category: form.category || undefined,
      keyword: form.keyword || undefined,
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}
</script>
