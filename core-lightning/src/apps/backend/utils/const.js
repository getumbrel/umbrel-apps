/* eslint-disable id-length */
module.exports = {
  REQUEST_CORRELATION_NAMESPACE_KEY: "umbrel-lightning-request",
  REQUEST_CORRELATION_ID_KEY: "reqId",

  LIGHTNING_LOCAL_SERVICE:
    process.env.LIGHTNING_LOCAL_SERVICE || "umbrel.local",

  LIGHTNING_HOST: process.env.LIGHTNING_HOST || "lightning", // contianer name
  LIGHTNING_GRPC_PORT: process.env.LIGHTNING_GRPC_PORT || 8001,
  LIGHTNING_NETWORK: process.env.LIGHTNING_NETWORK || "mainnet",
  LIGHTNING_REST_PORT: process.env.LIGHTNING_REST_PORT,
  LIGHTNING_REST_MACAROON_PATH: process.env.LIGHTNING_REST_MACAROON_PATH,
  LIGHTNING_REST_HIDDEN_SERVICE: process.env.LIGHTNING_REST_HIDDEN_SERVICE,
  LOCAL_HOST: process.env.LOCAL_HOST,
};
