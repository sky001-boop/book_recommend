<template>
  <div id="app-root">
    <AppHeader v-if="userStore.isLoggedIn" />
    <main :class="{ 'has-header': userStore.isLoggedIn }">
      <router-view v-slot="{ Component }">
        <transition name="slide-up" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { useUserStore } from './stores/user'
import AppHeader from './components/AppHeader.vue'

const userStore = useUserStore()
</script>

<style scoped>
#app-root {
  min-height: 100vh;
}
main {
  min-height: calc(100vh - 64px);
}
main.has-header {
  padding-top: 0;
}
</style>
