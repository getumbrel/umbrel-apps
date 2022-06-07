import API from "@/helpers/api";

// Initial state
const state = () => ({
  version: "",
  connectionInfo: {
    port: "",
    macaroon: "",
    torHost: "",
    localHost: "",
  },
  syncPercent: 0,
});

// Functions to update the state directly
const mutations = {
  setVersion(state, version) {
    state.version = version;
  },

  setConnectionInfo(state, connectionInfo) {
    state.connectionInfo = connectionInfo;
  },

  setSyncPercent(state, percent) {
    state.syncPercent = percent;
  },
};

// Functions to get data from the API
const actions = {
  async getConnectionInformation({ commit }) {
    const connectionInfo = await API.get(`/v1/lightning/connection-details`);

    if (connectionInfo) {
      commit("setConnectionInfo", connectionInfo);
    }
  },

  async getVersion({ commit }) {
    const version = await API.get(`/v1/lightning/version`);

    if (version) {
      commit("setVersion", version);
    }
  },

  async getSyncPercent({ commit }) {
    const syncPercent = await API.get(`/v1/lightning/syncPercent`);

    if (syncPercent) {
      commit("setSyncPercent", syncPercent);
    }
  },
};

const getters = {};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
