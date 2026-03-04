const express = require("express");
const net = require("net");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 18081;

const ELECTRUMX_RPC_HOST = process.env.ELECTRUMX_RPC_HOST || "127.0.0.1";
const ELECTRUMX_RPC_PORT = parseInt(process.env.ELECTRUMX_RPC_PORT || "8010");
const ELECTRUMX_TCP_PORT = process.env.ELECTRUMX_TCP_PORT || "50011";
const ELECTRUMX_SSL_PORT = process.env.ELECTRUMX_SSL_PORT || "50012";
const ELECTRUM_HIDDEN_SERVICE = process.env.ELECTRUM_HIDDEN_SERVICE || "";
const ELECTRUM_LOCAL_SERVICE = process.env.ELECTRUM_LOCAL_SERVICE || "";

function rpcCall(method, params = []) {
  return new Promise((resolve, reject) => {
    const socket = new net.Socket();
    let data = "";

    socket.setTimeout(10000);

    socket.connect(ELECTRUMX_RPC_PORT, ELECTRUMX_RPC_HOST, () => {
      const request =
        JSON.stringify({
          jsonrpc: "2.0",
          id: Date.now(),
          method,
          params,
        }) + "\n";
      socket.write(request);
    });

    socket.on("data", (chunk) => {
      data += chunk.toString();
      if (data.includes("\n")) {
        socket.destroy();
        try {
          const lines = data.trim().split("\n");
          const parsed = JSON.parse(lines[lines.length - 1]);
          if (parsed.error) {
            reject(new Error(JSON.stringify(parsed.error)));
          } else {
            resolve(parsed.result);
          }
        } catch (e) {
          reject(e);
        }
      }
    });

    socket.on("error", reject);
    socket.on("timeout", () => {
      socket.destroy();
      reject(new Error("RPC request timed out"));
    });
  });
}

app.use(express.static(path.join(__dirname, "public")));

app.get("/api/status", async (req, res) => {
  try {
    const info = await rpcCall("getinfo");

    let sessionCount = 0;
    try {
      const sessions = await rpcCall("sessions");
      sessionCount = Array.isArray(sessions) ? sessions.length : 0;
    } catch (e) {
      // sessions call may fail during sync
    }

    res.json({
      version: info.version || "unknown",
      dbHeight: info.db_height,
      daemonHeight: info.daemon_height,
      syncProgress:
        info.daemon_height > 0
          ? ((info.db_height / info.daemon_height) * 100).toFixed(2)
          : "0.00",
      synced: info.db_height >= info.daemon_height - 1,
      sessions: sessionCount,
      txCount: info.txcount,
      coin: info.coin || "Namecoin",
      network: info.network || "mainnet",
      tcpPort: ELECTRUMX_TCP_PORT,
      sslPort: ELECTRUMX_SSL_PORT,
      hiddenService: ELECTRUM_HIDDEN_SERVICE,
      localService: ELECTRUM_LOCAL_SERVICE,
    });
  } catch (err) {
    res.json({
      error: err.message,
      tcpPort: ELECTRUMX_TCP_PORT,
      sslPort: ELECTRUMX_SSL_PORT,
      hiddenService: ELECTRUM_HIDDEN_SERVICE,
      localService: ELECTRUM_LOCAL_SERVICE,
    });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Namecoin ElectrumX web dashboard on port ${PORT}`);
});
