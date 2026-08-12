<template>
  <div class="layout">
    <header class="topbar">
      <router-link to="/" class="brand">AI 热点分析</router-link>
      <nav>
        <router-link to="/">首页</router-link>
        <router-link to="/history">历史检索</router-link>
      </nav>
    </header>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts"></script>
