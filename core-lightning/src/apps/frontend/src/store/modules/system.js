import API from "@/helpers/api";

// Initial state
const state = () => ({
  version: "",
  api: {
    operational: false,
    version: "",
  },
});

// Functions to update the state directly
const mutations = {
  setVersion(state, version) {
    state.version = version;
  },
  setApi(state, api) {
    state.api = api;
  },
};

// Functions to get data from the API
const actions = {
  async getVersion({ commit }) {
    const data = await API.get(`/v1/system/info`);
    if (data && data.version) {
      let { version } = data;
      if (data.build) {
        version += `-build-${data.build}`;
      }
      commit("setVersion", version);
    }
  },
  async getApi({ commit }) {
    const api = await API.get(`/ping`);
    commit("setApi", {
      operational: !!(api && api.version),
      version: api && api.version ? api.version : "",
    });
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
