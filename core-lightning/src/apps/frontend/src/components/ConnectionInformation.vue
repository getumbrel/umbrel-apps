<template>
  <div class="mt-16">
    <p class="mb-8 text-neutral-900 dark:text-neutral-300 text-lg">
      Use the following details to connect your wallet or application to Core
      Lightning.
    </p>
    <div class="flex flex-col md:grid md:grid-cols-12 md:gap-8">
      <div
        class="flex justify-center mt-8 md:mt-0 sm:text-center md:max-w-2xl md:mx-auto md:col-span-4 md:text-left md:items-center"
      >
        <div class="max-w-fit p-4 bg-white rounded-lg shadow">
          <!-- QR Code -->
          <qr-code
            :value="connectionString"
            :size="220"
            class="qr-image mx-auto"
            showLogo
          ></qr-code>
        </div>
      </div>
      <div class="mt-4 md:col-span-8">
        <!-- RPC Section -->
        <div class="flex flex-col space-y-4 items-center md:items-start">
          <div class="max-w-xs w-full">
            <div class="rounded-full p-1 bg-slate-200 dark:bg-zinc-700">
              <div class="relative z-0 rounded-full">
                <button
                  class="rounded-full px-4 py-2 w-1/2 font-medium dark:text-white transition whitespace-nowrap"
                  :class="{
                    'text-white duration-500': selectedNetwork === 'local',
                    'text-slate-800': selectedNetwork !== 'local',
                  }"
                  @click="selectLocal"
                >
                  Local Network
                </button>
                <button
                  class="rounded-full px-4 py-2 w-1/2 font-medium dark:text-white transition"
                  :class="{
                    'text-white duration-500': selectedNetwork === 'tor',
                    'text-slate-800': selectedNetwork !== 'tor',
                  }"
                  @click="selectTor"
                >
                  Tor
                </button>
                <!-- Selection Pill -->
                <span
                  class="transform transition duration-500 ease-in-out absolute top-0 left-0 h-10 w-1/2 bg-umbrel rounded-full shadow-md"
                  :class="{
                    'translate-x-full': selectedNetwork === 'tor',
                  }"
                  style="z-index: -1"
                ></span>
              </div>
            </div>
          </div>
          <div class="mt-6 grid grid-cols-1 gap-y-6 gap-x-4 md:grid-cols-6 w-full">
            <div class="flex flex-col md:col-span-3">
              <label
                class="mb-1 d-block text-sm font-bold uppercase dark:text-slate-300"
                >Node Interface</label
              >
              <div v-if="connectionInfo">
                <input-copy
                  class="mb-2"
                  size="sm"
                  value="c-lightning-REST"
                ></input-copy>
              </div>
              <span
                class="loading-placeholder loading-placeholder-lg mt-1"
                style="width: 100%;"
                v-else
              ></span>
            </div>
            <div class="flex flex-col md:col-span-3">
              <label
                class="mb-1 d-block text-sm font-bold uppercase dark:text-slate-300"
                >Host</label
              >
              <div v-if="connectionInfo">
                <input-copy
                  class="mb-2"
                  size="sm"
                  :value="selectedNetwork === 'tor' ? connectionInfo.torHost :  connectionInfo.localHost"
                ></input-copy>
              </div>
              <span
                class="loading-placeholder loading-placeholder-lg mt-1"
                style="width: 100%;"
                v-else
              ></span>
            </div>
          </div>
          <div
            class="mt-6 grid grid-cols-1 gap-y-6 gap-x-4 md:grid-cols-6 w-full"
          >
            <div class="flex flex-col md:col-span-3">
              <label
                class="mb-1 d-block text-sm font-bold uppercase dark:text-slate-300"
                >Port</label
              >
              <div v-if="connectionInfo">
                <input-copy
                  class="mb-2"
                  size="sm"
                  :value="connectionInfo.port"
                ></input-copy>
              </div>
              <span
                class="loading-placeholder loading-placeholder-lg mt-1"
                style="width: 100%;"
                v-else
              ></span>
            </div>
            <div class="flex flex-col md:col-span-3">
              <label
                class="mb-1 d-block text-sm font-bold uppercase dark:text-slate-300"
                >Macaroon</label
              >
              <div v-if="connectionInfo">
                <!-- only show value if other connection info has come through -->
                <input-copy
                  class="mb-2"
                  size="sm"
                  :value="connectionInfo.macaroon"
                ></input-copy>
              </div>
              <span
                class="loading-placeholder loading-placeholder-lg mt-1"
                style="width: 100%;"
                v-else
              ></span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div
      class="mt-12 border-t border-gray-300 space-x-6 flex whitespace-nowrap dark:border-slate-200 dark:border-opacity-20"
    >
      <p
        class="mt-12 text-neutral-900 dark:text-neutral-300 text-lg whitespace-normal"
      >
        Looking for step-by-step instructions to connect your wallet to Core
        Lightning?
        <a href="https://link.umbrel.com/connect-core-lightning">Click here</a>.
      </p>
    </div>
  </div>
</template>

<script>
import { mapState } from "vuex";
import QrCode from "@/components/Utility/QrCode";
import InputCopy from "@/components/Utility/InputCopy";

export default {
  data() {
    return {
      selectedNetwork: "local",
    };
  },
  methods: {
    selectTor: function() {
      this.selectedNetwork = "tor";
    },
    selectLocal: function() {
      this.selectedNetwork = "local";
    },
  },
  computed: {
    ...mapState({
      connectionInfo: function(state) {
        return state.lightning.connectionInfo;
      },
      connectionString: function(state) {
        const {
          port,
          macaroon,
          torHost,
          localHost,
        } = state.lightning.connectionInfo;
        const host = this.selectedNetwork === "tor" ? torHost : localHost;
        const string = `c-lightning-rest://${host}:${port}?macaroon=${macaroon}&protocol=http`;
        
        return string;
      },
    }),
  },
  components: {
    QrCode,
    InputCopy,
  },
};
</script>
