const express = require("express");
const http = require("http");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 18080;

const NAMECOIND_HOST = process.env.NAMECOIND_HOST || "localhost";
const NAMECOIND_RPC_PORT = process.env.NAMECOIND_RPC_PORT || "8336";
const NAMECOIND_RPC_USER = process.env.NAMECOIND_RPC_USER || "umbrel";
const NAMECOIND_RPC_PASS = process.env.NAMECOIND_RPC_PASS || "namecoinrpc";

function rpcCall(method, params = []) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      jsonrpc: "1.0",
      id: Date.now(),
      method,
      params,
    });

    const options = {
      hostname: NAMECOIND_HOST,
      port: parseInt(NAMECOIND_RPC_PORT),
      path: "/",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization:
          "Basic " +
          Buffer.from(`${NAMECOIND_RPC_USER}:${NAMECOIND_RPC_PASS}`).toString(
            "base64"
          ),
      },
      timeout: 10000,
    };

    const req = http.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            reject(new Error(parsed.error.message));
          } else {
            resolve(parsed.result);
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("Request timed out"));
    });
    req.write(body);
    req.end();
  });
}

app.use(express.static(path.join(__dirname, "public")));

app.get("/api/status", async (req, res) => {
  try {
    const [blockchainInfo, networkInfo, mempoolInfo] = await Promise.all([
      rpcCall("getblockchaininfo"),
      rpcCall("getnetworkinfo"),
      rpcCall("getmempoolinfo"),
    ]);

    res.json({
      chain: blockchainInfo.chain,
      blocks: blockchainInfo.blocks,
      headers: blockchainInfo.headers,
      verificationProgress: blockchainInfo.verificationprogress,
      initialBlockDownload: blockchainInfo.initialblockdownload,
      sizeOnDisk: blockchainInfo.size_on_disk,
      pruned: blockchainInfo.pruned,
      connections: networkInfo.connections,
      version: networkInfo.subversion,
      protocolVersion: networkInfo.protocolversion,
      mempoolSize: mempoolInfo.size,
      rpcUser: NAMECOIND_RPC_USER,
      rpcPass: NAMECOIND_RPC_PASS,
      rpcPort: NAMECOIND_RPC_PORT,
      p2pPort: "8334",
    });
  } catch (err) {
    res.json({
      error: err.message,
      rpcUser: NAMECOIND_RPC_USER,
      rpcPass: NAMECOIND_RPC_PASS,
      rpcPort: NAMECOIND_RPC_PORT,
      p2pPort: "8334",
    });
  }
});

app.get("/api/name/:name", async (req, res) => {
  try {
    const result = await rpcCall("name_show", [req.params.name]);
    res.json(result);
  } catch (err) {
    res.json({ error: err.message });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Namecoin Core info server running on port ${PORT}`);
});
