// State
let pollInterval;
let activePaymentHash = null;
let purchaseMode = "buy"; // "buy" or "renew"
// Initialization
document.addEventListener("DOMContentLoaded", () => {
    fetchStatus();
    fetchServers();
});

// UI Routing
function switchTab(tabId) {
    document.querySelectorAll('main > section').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('nav > button').forEach(el => {
        el.classList.remove('tab-active', 'font-bold');
        el.classList.add('text-gray-400');
    });

    document.getElementById(`view-${tabId}`).classList.remove('hidden');
    const btn = document.getElementById(`tab-${tabId}`);
    btn.classList.add('tab-active');
    btn.classList.remove('text-gray-400');
}

// 1. Fetch Local Status
async function fetchStatus() {
    try {
        const res = await fetch('/api/local/status');
        const data = await res.json();

        // Update Header Badge
        const badge = document.getElementById('statusBadge');
        if (data.wg_status === 'Connected') {
            badge.className = "px-4 py-2 rounded-full font-bold text-sm bg-green-900/50 text-tsgreen border border-green-700";
            badge.innerText = "Tunnel Active";
            document.getElementById('txt-wg-status').className = "font-mono text-tsgreen font-bold";
        } else {
            badge.className = "px-4 py-2 rounded-full font-bold text-sm bg-red-900/50 text-red-500 border border-red-700";
            badge.innerText = "Tunnel Down";
            document.getElementById('txt-wg-status').className = "font-mono text-red-500 font-bold";
        }

        // Update Dashboard Text
        document.getElementById('txt-wg-status').innerText = data.wg_status;
        const pk = data.wg_pubkey || "Not available";
        document.getElementById('txt-pubkey').innerText = pk;

        // Setup pubkey for renewal
        document.getElementById('renew-pubkey').value = pk;
        if (pk !== "Not available" && purchaseMode === "buy") {
            // If there's an active status at load, suggest Renew instead of Buy
            purchaseMode = "renew"; // Will be applied visually via JS if needed, but safe to just let the UI handle it via setPurchaseMode.
        }

        let confs = data.configs_found.length > 0 ? data.configs_found.join(", ") : "None Detected";
        document.getElementById('txt-configs').innerText = confs;

        document.getElementById('txt-lnd-ip').innerText = data.lnd_ip || "Not Detected";
        document.getElementById('txt-cln-ip').innerText = data.cln_ip || "Not Detected";

    } catch (e) {
        console.error("Failed to fetch status", e);
    }
}

// 2. Fetch Servers
async function fetchServers() {
    try {
        const res = await fetch('/api/servers');
        const servers = await res.json();
        const sel = document.getElementById('server-select');
        sel.innerHTML = "";
        servers.forEach(s => {
            let opt = document.createElement('option');
            opt.value = s.id;
            opt.innerText = `${s.country} - ${s.city} (Port: ${s.wireguardPort})`;
            sel.appendChild(opt);
        });
    } catch (e) { }
}

// Purchase / Renew Mode Switch
function setPurchaseMode(mode) {
    purchaseMode = mode;
    const title = document.getElementById('purchase-title');
    const desc = document.getElementById('purchase-desc');
    const pubBox = document.getElementById('renew-pubkey-box');
    const btnBuy = document.getElementById('mode-buy');
    const btnRenew = document.getElementById('mode-renew');

    if (mode === 'buy') {
        title.innerText = "Buy New Subscription";
        desc.innerText = "Select a regional server, generate a Lightning Invoice, and scan to pay. Your VPN config will securely auto-install after payment.";
        pubBox.classList.add('hidden');
        btnBuy.className = "px-4 py-1.5 rounded bg-slate-700 text-white font-semibold text-sm transition shadow";
        btnRenew.className = "px-4 py-1.5 rounded text-gray-400 font-semibold text-sm hover:text-white transition";
    } else {
        title.innerText = "Renew Existing Target";
        desc.innerText = "Extend the duration of your active subscription. You don't need to reinstall the VPN configuration.";
        pubBox.classList.remove('hidden');
        btnRenew.className = "px-4 py-1.5 rounded bg-slate-700 text-white font-semibold text-sm transition shadow";
        btnBuy.className = "px-4 py-1.5 rounded text-gray-400 font-semibold text-sm hover:text-white transition";
    }
}

// 3. Purchase Flow
async function createSub() {
    const serverId = document.getElementById('server-select').value;
    const duration = parseInt(document.getElementById('duration-select').value);

    if (!serverId) return;

    document.getElementById('btn-create').innerText = "Loading...";
    document.getElementById('btn-create').disabled = true;

    try {
        let endpoint = '/api/subscription/create';
        let payload = { serverId, duration, referralCode: null };

        if (purchaseMode === 'renew') {
            endpoint = '/api/subscription/renew';
            const wgPublicKey = document.getElementById('renew-pubkey').value;
            payload = { serverId, duration, wgPublicKey };
            if (!wgPublicKey || wgPublicKey === "Not available") {
                alert("Cannot renew without an active public key from a connected VPN.");
                document.getElementById('btn-create').innerText = "Generate Lightning Invoice";
                document.getElementById('btn-create').disabled = false;
                return;
            }
        }

        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.paymentHash && data.invoice) {
            activePaymentHash = data.paymentHash;
            document.getElementById('invoice-bolt11').value = data.invoice;
            document.getElementById('pay-link').href = `lightning:${data.invoice}`;
            document.getElementById('invoice-box').classList.remove('hidden');

            // Start Polling
            pollInterval = setInterval(pollPayment, 3000);
        }
    } catch (e) {
        alert("Error creating subscription: " + e.message);
    } finally {
        document.getElementById('btn-create').innerText = "Generate Lightning Invoice";
        document.getElementById('btn-create').disabled = false;
    }
}

async function pollPayment() {
    if (!activePaymentHash) return;

    try {
        const res = await fetch(`/api/subscription/${activePaymentHash}`);
        const data = await res.json();

        if (data.status === 'PAID') {
            clearInterval(pollInterval);
            if (purchaseMode === 'buy') {
                document.getElementById('invoice-box').innerHTML = `<h3 class="text-tsgreen font-bold text-center mb-2">Payment Received!</h3><p class="text-sm text-gray-300 text-center">Provisioning VPN config...</p>`;
                claimSubscription();
            } else {
                document.getElementById('invoice-box').innerHTML = `<h3 class="text-tsgreen font-bold text-center mb-2">Renewal Successful!</h3><p class="text-sm text-gray-300 text-center mb-4">Your VPN subscription has been extended successfully. No restarts required.</p><button onclick="switchTab('dashboard');" class="mt-4 w-full bg-tsyellow hover:bg-yellow-500 text-black font-bold py-2 px-6 rounded transition">Return to Dashboard</button>`;
            }
        }
    } catch (e) { }
}

async function claimSubscription() {
    try {
        const res = await fetch('/api/subscription/claim', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paymentHash: activePaymentHash, referralCode: null })
        });

        if (res.ok) {
            const configMsg = await configureNode();
            document.getElementById('invoice-box').innerHTML = `<h3 class="text-tsgreen font-bold text-center mb-2">Installation Complete!</h3><p class="text-sm text-gray-300 text-center mb-2">Your VPN configuration has been securely stored.</p><p class="text-xs text-tsyellow text-center mb-4">${configMsg}</p><button onclick="restartTunnel(); switchTab('dashboard');" class="mt-4 w-full bg-tsyellow hover:bg-yellow-500 text-black font-bold py-2 px-6 rounded transition">Restart Apps & Tunnel</button>`;
        } else {
            document.getElementById('invoice-box').innerHTML = `<h3 class="text-red-500 font-bold text-center mb-2">Provisioning Error</h3><p class="text-sm text-gray-300 text-center">Payment was successful, but config provisioning failed.</p>`;
        }
    } catch (e) { }
}

async function configureNode() {
    try {
        const res = await fetch('/api/local/configure-node', { method: 'POST' });
        const data = await res.json();

        let msg = "";
        if (data.lnd && data.cln) msg = "LND and CLN were auto-configured!";
        else if (data.lnd) msg = "LND was auto-configured! Please restart LND via UI.";
        else if (data.cln) msg = "CLN was auto-configured! Please restart CLN via UI.";
        else msg = "Auto-config unavailable due to Umbrel permissions. Please follow the manual setup guide.";

        return msg;
    } catch (e) {
        return "Auto-config unavailable. Please configure manually.";
    }
}

// 4. Import Config
async function importConfig() {
    const txt = document.getElementById('config-text').value;
    const msg = document.getElementById('import-msg');

    msg.innerText = "Importing...";
    msg.className = "text-center mt-4 text-sm text-gray-400";

    try {
        const formData = new FormData();
        formData.append('config_text', txt);

        const res = await fetch('/api/local/upload-config', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        if (res.ok) {
            const configMsg = await configureNode();
            msg.innerText = `Config imported successfully! ${configMsg}`;
            msg.className = "text-center mt-4 text-sm font-bold text-tsgreen";
            setTimeout(() => {
                restartTunnel();
                switchTab('dashboard');
            }, 3000);
        } else {
            msg.innerText = data.error || "Import failed.";
            msg.className = "text-center mt-4 text-sm font-bold text-red-500";
        }
    } catch (e) {
        msg.innerText = e.message;
        msg.className = "text-center mt-4 text-sm font-bold text-red-500";
    }
}

async function restartTunnel() {
    try {
        await fetch('/api/local/restart', { method: 'POST' });
        // The container entrypoint will catch the trigger file, and restart `wg-quick`
        setTimeout(fetchStatus, 3000);
    } catch (e) { }
}
