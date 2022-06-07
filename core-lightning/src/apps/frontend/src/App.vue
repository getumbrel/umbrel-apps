<template>
  <div id="app" class="min-h-full bg-slate-100 dark:bg-neutral-800 w-full">
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
      <transition name="loading" mode>
        <div v-if="isIframe">
          <div class="flex col items-center justify-center">
            <img alt="Umbrel" src="@/assets/logo.svg" class="mb-5 logo" />
            <span class="text-muted w-75 text-center">
              <small
                >For security reasons Umbrel cannot be embedded in an
                iframe.</small
              >
            </span>
          </div>
        </div>
        <loading v-else-if="loading" :progress="loadingProgress"> </loading>
        <!-- component matched by the route will render here -->
        <router-view v-else></router-view>
      </transition>
    </div>
  </div>
</template>

<style lang="scss">
@import "@/styles/index.scss";
</style>

<script>
import Loading from "@/components/Loading";
import { mapState } from "vuex";

export default {
  name: "App",
  data() {
    return {
      isIframe: window.self !== window.top,
      loading: true,
      loadingProgress: 0,
      loadingPollInProgress: false,
    };
  },
  computed: {
    ...mapState({
      isApiOperational: (state) => {
        return state.system.api.operational;
      },
    }),
  },
  methods: {
    async getLoadingStatus() {
      // Skip if previous poll in progress or if system is updating
      if (this.loadingPollInProgress || this.updating) {
        return;
      }

      this.loadingPollInProgress = true;

      // Then check if middleware api is up
      if (this.loadingProgress <= 40) {
        this.loadingProgress = 40;
        await this.$store.dispatch("system/getApi");
        if (!this.isApiOperational) {
          this.loading = true;
          this.loadingPollInProgress = false;
          return;
        }
      }

      this.loadingProgress = 100;
      this.loadingPollInProgress = false;

      // Add slight delay so the progress bar makes
      // it to 100% before disappearing
      setTimeout(() => (this.loading = false), 300);
    },
  },
  created() {
    document.title = "Core Lightning - Umbrel";
  },
  watch: {
    loading: {
      handler: function(isLoading) {
        window.clearInterval(this.loadingInterval);
        //if loading, check loading status every two seconds
        if (isLoading) {
          this.loadingInterval = window.setInterval(
            this.getLoadingStatus,
            2000
          );
        } else {
          //else check every 20s
          this.loadingInterval = window.setInterval(
            this.getLoadingStatus,
            20000
          );
        }
      },
      immediate: true,
    },
  },
  beforeDestroy() {
    window.removeEventListener("resize", this.updateViewPortHeightCSS);
    window.clearInterval(this.loadingInterval);
  },
  components: {
    Loading,
  },
};
</script>

<style lang="scss" scoped>
// Loading transitions

.loading-enter-active,
.loading-leave-active {
  transition: opacity 0.4s ease;
}
.loading-enter {
  opacity: 0;
  // filter: blur(70px);
}
.loading-enter-to {
  opacity: 1;
  // filter: blur(0);
}
.loading-leave {
  opacity: 1;
  // filter: blur(0);
}
.loading-leave-to {
  opacity: 0;
  // filter: blur(70px);
}

.system-alert {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
}
</style>
