<template>
  <div class="star-rating" :class="{ readonly: readonly }">
    <span
      v-for="i in maxStars"
      :key="i"
      class="star"
      :class="{ filled: i <= displayValue, half: halfStar === i }"
      @click="!readonly && handleClick(i)"
      @mouseenter="!readonly && (hoverValue = i)"
      @mouseleave="!readonly && (hoverValue = 0)"
    >
      <el-icon :size="size">
        <StarFilled v-if="i <= displayValue" />
        <Star v-else />
      </el-icon>
    </span>
    <span v-if="showValue" class="star-value">{{ modelValue }}</span>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: { type: Number, default: 0 },
  maxStars: { type: Number, default: 10 },
  readonly: { type: Boolean, default: false },
  size: { type: Number, default: 18 },
  showValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const hoverValue = ref(0)
const displayValue = computed(() => hoverValue.value || props.modelValue)
const halfStar = computed(() => 0)

function handleClick(value) {
  emit('update:modelValue', value)
}
</script>

<style scoped>
.star-rating {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.star {
  cursor: pointer;
  color: #ddd;
  transition: color 0.15s, transform 0.15s;
}
.star:hover {
  transform: scale(1.2);
}
.star.filled {
  color: #F5A623;
}
.star.half {
  color: #F5A623;
}
.star.readonly {
  cursor: default;
}
.star-value {
  margin-left: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
}
</style>
