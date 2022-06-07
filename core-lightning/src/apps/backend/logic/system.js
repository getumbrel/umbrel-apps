const constants = require("utils/const.js");
const NodeError = require("models/errors.js").NodeError;
const fs = require('fs');

async function getLightningConnectionDetails() {
  try {
    const port = constants.LIGHTNING_REST_PORT;
    const macaroon = (await fs.promises.readFile(constants.LIGHTNING_REST_MACAROON_PATH)).toString('hex');

    const torHost = constants.LIGHTNING_REST_HIDDEN_SERVICE;
    const localHost = constants.LOCAL_HOST;

    return {
      port,
      macaroon,
      torHost,
      localHost,
    };
  } catch (error) {
    console.log("error: ", error);
    throw new NodeError("Unable to get Lightning hidden service url");
  }
}

module.exports = {
  getLightningConnectionDetails,
};
