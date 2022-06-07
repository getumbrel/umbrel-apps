/* eslint-disable camelcase, max-lines */
const grpc = require("grpc");
const path = require("path");
const camelizeKeys = require("camelize-keys");
const fs = require("fs");
const constants = require("utils/const.js");

const LightningError = require("models/errors.js").LightningError;

const LIGHTNING_HOST = constants.LIGHTNING_HOST;
const LIGHTNING_GRPC_PORT = constants.LIGHTNING_GRPC_PORT;
const LIGHTNING_NETWORK = constants.LIGHTNING_NETWORK;

const ROOT_CERT =
  process.env.CA_CERT || "/data/lightning/" + LIGHTNING_NETWORK + "/ca.pem";
const CLIENT_KEY =
  process.env.CLIENT_KEY ||
  "/data/lightning/" + LIGHTNING_NETWORK + "/client-key.pem";
const CLIENT_CERT =
  process.env.CLIENT_CERT ||
  "/data/lightning/" + LIGHTNING_NETWORK + "/client.pem";

const PROTO_FILE = process.env.PROTO_FILE || "./resources/rpc.proto";

// TODO move this to volume
const clnDescriptor = grpc.load(PROTO_FILE);
const cln = clnDescriptor.cln;

const DEFAULT_RECOVERY_WINDOW = 250;
const GRPC_PARAMS = {
  "grpc.max_receive_message_length": -1,
  "grpc.max_send_message_length": -1,
  "grpc.ssl_target_name_override": "cln",
};

// Initialize RPC client will attempt to connect to the clightning rpc with a root cert, client key, and client cert.
// There isn't a concept of creating or unlocking a wallet like in LND.
async function initializeRPCClient() {
  const [root, key, cert] = await Promise.all([
    fs.readFileSync(ROOT_CERT),
    fs.readFileSync(CLIENT_KEY),
    fs.readFileSync(CLIENT_CERT),
  ]);

  const credentials = grpc.credentials.createSsl(root, key, cert);

  return {
    lightning: new cln.Node(
      LIGHTNING_HOST + ":" + LIGHTNING_GRPC_PORT,
      credentials,
      GRPC_PARAMS
    ),
    state: true, // eslint-disable-line object-shorthand
  };
}

async function promiseify(rpcObj, rpcFn, payload, description) {
  return new Promise((resolve, reject) => {
    try {
      rpcFn.call(rpcObj, payload, (error, grpcResponse) => {
        if (error) {
          reject(new LightningError(`Unable to ${description}`, error));
        } else {
          resolve(camelizeKeys(grpcResponse, "_"));
        }
      });
    } catch (error) {
      reject(error);
    }
  });
}

function getInfo() {
  return initializeRPCClient().then(({ lightning }) =>
    promiseify(lightning, lightning.Getinfo, {}, "get lightning information")
  );
}

module.exports = {
  getInfo,
};
