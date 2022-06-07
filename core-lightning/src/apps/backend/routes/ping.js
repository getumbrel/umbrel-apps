const express = require('express');
const pjson = require('../package.json');
const router = express.Router();

router.get('/', function (req, res) {
  res.json({ version: 'umbrel-middleware-' + pjson.version });
});

module.exports = router;
