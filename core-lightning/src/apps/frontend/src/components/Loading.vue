<template>
  <div
    class="h-screen flex flex-col items-center justify-center min-h-full p-2"
  >
    <img alt="Umbrel" src="@/assets/logo.svg" class="mb-16 logo" />

    <div class="w-1/4 mb-2">
      <progress-bar :percentage="progress" class="h-1"></progress-bar>
    </div>
    <slot></slot>
  </div>
</template>

<script>
import ProgressBar from "@/components/Utility/ProgressBar";

export default {
  data() {
    return {};
  },
  props: { progress: Number },
  created() {},
  methods: {},
  components: {
    ProgressBar,
  },
};
</script>

<style lang="scss">
.logo {
  height: 20vh;
  max-height: 200px;
  width: auto;
}
</style>
