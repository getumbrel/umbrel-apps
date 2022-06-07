<template>
  <div class="py-14">
    <lightning-header></lightning-header>
    <connection-information></connection-information>
  </div>
</template>

<script>
import ConnectionInformation from "@/components/ConnectionInformation";
import Header from "@/components/Header";

export default {
  data() {
    return {};
  },
  methods: {},
  created() {
    this.$store.dispatch("lightning/getConnectionInformation");
  },
  beforeDestroy() {},
  components: {
    ConnectionInformation,
    lightningHeader: Header,
  },
};
</script>
