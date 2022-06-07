<template>
  <div
    class="w-full bg-gray-200 dark:bg-neutral-700 h-1 relative overflow-hidden rounded-full"
  >
    <div
      class="h-full progressbar rounded-full"
      :class="colorClass"
      role="progressbar"
      :style="{ width: `${percentage}%` }"
      :aria-valuenow="percentage"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <span class="flex items-center h-full">
        <slot></slot>
      </span>
    </div>
  </div>
</template>
<script>
export default {
  props: {
    percentage: {
      type: Number,
      default: 0,
    },
    colorClass: {
      type: String,
      default: "bg-umbrel",
    },
  },
};
</script>
<style scoped>
@keyframes progress-indeterminate {
  0% {
    width: 30%;
    left: -40%;
  }
  60% {
    left: 100%;
    width: 100%;
  }
  to {
    left: 100%;
    width: 0;
  }
}
.progressbar {
  transition: width 0.25s ease;
}
.indeterminate .progressbar {
  animation: progress-indeterminate 1.4s ease infinite;
}
</style>
