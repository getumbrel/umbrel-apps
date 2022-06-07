import Vue from "vue";
import Vuex from "vuex";

//Modules
import system from "./modules/system";
import lightning from "./modules/lightning";

Vue.use(Vuex);

export default new Vuex.Store({
  modules: {
    system,
    lightning
  }
});
