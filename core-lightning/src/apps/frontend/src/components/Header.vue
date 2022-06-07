<template>
  <div class="flex justify-content-start align-items-center">
    <div
      class="bg-gray-800 dark:bg-gray-700 rounded-lg p-2 mr-6 w-28 h-28 flex items-center justify-center"
    >
      <img class="w-full h-full" src="@/assets/icon-app-lightning.svg" />
    </div>
    <div>
      <div class="flex items-center">
        <svg
          width="8"
          height="8"
          viewBox="0 0 8 8"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="4" cy="4" r="4" fill="#00CD98" />
        </svg>
        <p class="ml-1 text-green-400 text-lg">Running</p>
      </div>
      <h3 class="text-5xl font-semibold  dark:text-white">Core Lightning</h3>
      <span class="text-sm text-gray-500 font-medium">{{
        version ? `${version}` : "..."
      }}</span>
    </div>
  </div>
</template>

<script>
// import Vue from "vue";
import { mapState } from "vuex";

export default {
  data() {
    return {};
  },
  computed: {
    ...mapState({
      version: (state) => state.lightning.version,
    }),
  },
  created() {
    this.$store.dispatch("lightning/getVersion");
  },
};
</script>
