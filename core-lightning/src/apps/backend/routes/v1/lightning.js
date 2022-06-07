const express = require("express");
const router = express.Router();
const lightningService = require("services/lightning");

const systemLogic = require("logic/system.js");
const safeHandler = require("utils/safeHandler");

router.get(
  "/connection-details",
  safeHandler(async (req, res) => {
    const connectionDetails = await systemLogic.getLightningConnectionDetails();
    return res.status(200).json(connectionDetails);
  })
);

router.get(
  "/version",
  safeHandler(async (req, res) => {
    try {
      const { version } = await lightningService.getInfo();
      return res.status(200).json(version);
    } catch (e) {
      console.error("version error: ", e);
      return res.status(500).json(e);
    }
  })
);

module.exports = router;
