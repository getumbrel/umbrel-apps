/**
 * Transaction Analysis Tool
 * Transaction lookup, UTXO tracing, CoinJoin detection, and privacy scoring
 */

import { apiCall } from '../api.js';
import { showLoading, showError } from '../ui.js';
import { createTruncatedValue } from '../utils.js';

// Store current transaction data for tracing
let currentTxid = null;
let currentTraceData = null;

/**
 * Analyze transaction details
 */
export async function analyzeTransaction() {
    const txid = document.getElementById('txid-input').value.trim();
    if (!txid) {
        alert('Please enter a transaction ID');
        return;
    }
    currentTxid = txid;
    showLoading();
    try {
        const tx = await apiCall('/transactions/' + txid, { resolve_inputs: true });
        renderTx(tx);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render transaction details
 * @param {Object} tx - Transaction data
 */
function renderTx(tx) {
    // Format transaction date
    var txDateDisplay = '-';
    var txDateFull = '';
    if (tx.block_time) {
        var txDate = new Date(tx.block_time * 1000);
        txDateDisplay = txDate.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
        txDateFull = txDate.toLocaleString();
    }

    let html = '<div class="card"><div class="card-header"><div class="card-title">📋 Transaction Details</div>';
    if (tx.is_coinbase) html += '<span class="cj-badge medium">⛏️ Coinbase</span>';
    html += '</div><div class="card-body"><div class="tx-details">';
    html += '<div class="tx-row"><span class="tx-label">TXID</span><span class="tx-value">' + createTruncatedValue(tx.txid, tx.txid.substring(0, 16) + '...', 'tx-txid') + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Date</span><span class="tx-value" title="' + txDateFull + '">' + txDateDisplay + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Block Height</span><span class="tx-value">' + (tx.block_height ? tx.block_height.toLocaleString() : 'Unconfirmed') + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Confirmations</span><span class="tx-value">' + (tx.confirmations ? tx.confirmations.toLocaleString() : '0') + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Size</span><span class="tx-value">' + tx.vsize + ' vB (' + tx.size + ' bytes)</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Fee</span><span class="tx-value">' + (tx.fee_sats ? tx.fee_sats.toLocaleString() + ' sats' : 'N/A') + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Total Output</span><span class="tx-value positive">' + (tx.total_output_btc ? tx.total_output_btc.toFixed(8) : '0') + ' BTC</span></div>';
    html += '</div></div></div>';

    html += '<div class="card"><div class="card-header"><div class="card-title">📥 Inputs (' + tx.input_count + ')</div></div><div class="card-body"><table class="io-table"><thead><tr><th title="Input index (vin)"># vin</th><th>Date</th><th>Previous TX</th><th>Address</th><th>Value</th></tr></thead><tbody>';
    for (var i = 0; i < tx.inputs.length; i++) {
        var inp = tx.inputs[i];
        var prevTxDisplay = inp.txid ? createTruncatedValue(inp.txid, inp.txid.substring(0, 16) + '...', 'tx-in-' + i) : 'Coinbase';
        var addrDisplay = inp.address ? createTruncatedValue(inp.address, inp.address.substring(0, 12) + '...' + inp.address.slice(-6), 'tx-in-addr-' + i) : '-';
        html += '<tr><td>' + i + '</td><td title="' + txDateFull + '">' + txDateDisplay + '</td><td class="mono">' + prevTxDisplay + '</td>';
        html += '<td class="mono">' + addrDisplay + '</td><td>' + (inp.value ? inp.value.toFixed(8) + ' BTC' : '-') + '</td></tr>';
    }
    html += '</tbody></table></div></div>';

    html += '<div class="card"><div class="card-header"><div class="card-title">📤 Outputs (' + tx.output_count + ')</div></div><div class="card-body"><table class="io-table"><thead><tr><th title="Output index (vout)"># vout</th><th>Date</th><th>Address</th><th>Type</th><th>Value</th></tr></thead><tbody>';
    for (var j = 0; j < tx.outputs.length; j++) {
        var out = tx.outputs[j];
        var outAddrDisplay = out.address ? createTruncatedValue(out.address, out.address.substring(0, 12) + '...' + out.address.slice(-6), 'tx-out-' + j) : 'OP_RETURN';
        html += '<tr><td>' + out.n + '</td><td title="' + txDateFull + '">' + txDateDisplay + '</td><td class="mono">' + outAddrDisplay + '</td>';
        html += '<td>' + out.type + '</td><td>' + out.value_btc.toFixed(8) + ' BTC</td></tr>';
    }
    html += '</tbody></table></div></div>';

    document.getElementById('results-container').innerHTML = html;
}

/**
 * Trace UTXO forward or backward
 */
export async function traceUTXO() {
    const txid = document.getElementById('txid-input').value.trim();
    if (!txid) {
        alert('Please enter a transaction ID');
        return;
    }
    const dir = document.getElementById('trace-direction').value;
    const depth = document.getElementById('trace-depth').value;
    const vout = document.getElementById('vout-input').value;
    showLoading();
    try {
        var result;
        if (dir === 'forward') {
            result = await apiCall('/analysis/trace/forward', { txid: txid, vout: vout, max_depth: depth });
        } else {
            result = await apiCall('/analysis/trace/backward', { txid: txid, max_depth: depth });
        }
        currentTraceData = result;
        currentTraceData._direction = dir;
        renderTrace(result, dir);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render trace results
 * @param {Object} result - Trace data
 * @param {string} dir - Direction (forward/backward)
 */
function renderTrace(result, dir) {
    const s = result.summary || {};
    let html = '<div class="stats-grid">';
    html += '<div class="stat-card"><div class="stat-value">' + (result.nodes ? result.nodes.length : 0) + '</div><div class="stat-label">Transactions</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (s.unspent_count || 0) + '</div><div class="stat-label">Unspent</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (s.coinjoin_count || 0) + '</div><div class="stat-label">Unique CoinJoins <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total unique CoinJoin transactions detected in the trace graph.</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + result.execution_time_ms + 'ms</div><div class="stat-label">Time</div></div>';
    html += '</div>';

    if (result.electrs_enabled) {
        html += '<div style="background: rgba(35, 134, 54, 0.1); border: 1px solid var(--accent-green); border-radius: 8px; padding: 12px; margin-bottom: 16px;"><span style="color: var(--accent-green);">✓ Fulcrum Enabled</span></div>';
    } else {
        html += '<div style="background: rgba(210, 153, 34, 0.1); border: 1px solid var(--accent-orange); border-radius: 8px; padding: 12px; margin-bottom: 16px;"><span style="color: var(--accent-orange);">⚠ Fulcrum Not Available</span></div>';
    }

    html += '<div class="card"><div class="card-header"><div class="card-title">🔎 Trace Results (' + dir + ')</div>';
    if (result.nodes && result.nodes.length > 0 && result.edges && result.edges.length > 0) {
        html += '<button class="btn-visualize" onclick="window.openVisualization()">🔗 Visualize Flow</button>';
    }
    html += '</div><div class="card-body">';

    if (result.nodes && result.nodes.length > 0) {
        // Build edge lookup
        var edgeLookup = {};
        var edgeLookupByTxid = {};
        if (result.edges) {
            for (var e = 0; e < result.edges.length; e++) {
                var edge = result.edges[e];
                var key = edge.from_txid + ':' + edge.from_vout;
                edgeLookup[key] = edge.to_txid;
                if (!edgeLookupByTxid[edge.from_txid]) {
                    edgeLookupByTxid[edge.from_txid] = edge.to_txid;
                }
            }
        }

        // Build node lookup by txid
        var nodeLookup = {};
        for (var j = 0; j < result.nodes.length; j++) {
            var node = result.nodes[j];
            if (!nodeLookup[node.txid]) nodeLookup[node.txid] = [];
            nodeLookup[node.txid].push(node);
        }

        html += '<table class="io-table"><thead><tr><th>Depth</th><th>Date</th><th>TXID</th><th>Address</th><th>Spent To</th><th>Value</th><th>Status</th><th>CoinJoin</th></tr></thead><tbody>';
        var nodes = result.nodes.slice(0, 50);
        for (var i = 0; i < nodes.length; i++) {
            var n = nodes[i];
            var statusIcon;
            if (n.status === 'unspent') {
                statusIcon = '<span title="Coins are still at this address (end of trail)" style="color: var(--accent-green);">💰 Unspent</span>';
            } else if (n.status === 'coinbase') {
                statusIcon = '<span title="Mining reward (origin of new coins)" style="color: var(--accent-yellow);">⛏️ Coinbase</span>';
            } else {
                statusIcon = '<span title="Coins moved to another transaction" style="color: var(--text-secondary);">📤 Spent</span>';
            }

            var cjBadge;
            if (n.coinjoin_score > 0.7) {
                cjBadge = '<span class="cj-badge high">🔀 ' + (n.coinjoin_score * 100).toFixed(0) + '%</span>';
            } else if (n.coinjoin_score > 0.3) {
                cjBadge = '<span class="cj-badge medium">' + (n.coinjoin_score * 100).toFixed(0) + '%</span>';
            } else {
                cjBadge = '<span class="cj-badge low">No</span>';
            }

            var addrDisplay;
            if (n.address) {
                addrDisplay = createTruncatedValue(n.address, n.address.substring(0, 12) + '...' + n.address.slice(-6), 'trace-addr-' + i);
            } else if (n.script_type === 'pubkey') {
                addrDisplay = '<span style="color: var(--accent-orange);" title="Pay-to-Public-Key (early Bitcoin format, no address)">P2PK</span>';
            } else if (n.script_type === 'nulldata' || n.script_type === 'op_return') {
                addrDisplay = '<span style="color: var(--text-secondary);" title="OP_RETURN data output, no recipient">OP_RETURN</span>';
            } else if (n.script_type === 'multisig') {
                addrDisplay = '<span style="color: var(--accent-purple);" title="Multisig output">Multisig</span>';
            } else if (n.script_type === 'nonstandard') {
                addrDisplay = '<span style="color: var(--text-secondary);" title="Non-standard script">Non-std</span>';
            } else {
                addrDisplay = '-';
            }

            // Find "Spent To"
            var spentToDisplay = '-';
            var spentToFull = '';
            if (n.status === 'unspent') {
                spentToDisplay = '<span style="color: var(--accent-green);">Unspent</span>';
            } else if (n.status === 'coinbase') {
                spentToDisplay = '<span style="color: var(--accent-yellow);">Origin</span>';
            } else if (n.depth === 0 && dir === 'backward') {
                spentToDisplay = '<span style="color: var(--accent-blue);">Start</span>';
            } else {
                var spentKey = n.txid + ':' + n.vout;
                var spentToTxid = edgeLookup[spentKey] || edgeLookupByTxid[n.txid] || n.spent_by_txid;
                if (spentToTxid) {
                    spentToDisplay = createTruncatedValue(spentToTxid, spentToTxid.substring(0, 8) + '...', 'spent-to-' + i);
                    spentToFull = spentToTxid;
                } else if (n.status === 'spent' && dir === 'forward') {
                    spentToDisplay = '<span style="color: var(--text-secondary);" title="Spent but destination unknown - Fulcrum lookup may have failed">Unknown</span>';
                } else if (dir === 'backward' && n.depth > 0) {
                    spentToDisplay = '<span style="color: var(--text-secondary);" title="Input transaction - edge data not available">Input</span>';
                }
            }

            // Format date
            var dateDisplay = '-';
            var dateTitle = '';
            if (n.block_time) {
                var d = new Date(n.block_time);
                dateDisplay = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
                dateTitle = d.toLocaleString();
            }

            var txidDisplay = createTruncatedValue(n.txid, n.txid.substring(0, 16) + '...', 'trace-txid-' + i);
            html += '<tr><td>' + n.depth + '</td><td title="' + dateTitle + '">' + dateDisplay + '</td><td class="mono">' + txidDisplay + '</td>';
            html += '<td class="mono">' + addrDisplay + '</td>';
            html += '<td class="mono" title="' + spentToFull + '">' + spentToDisplay + '</td>';
            html += '<td>' + (n.value_btc ? n.value_btc.toFixed(8) : '?') + ' BTC</td><td>' + statusIcon + '</td><td>' + cjBadge + '</td></tr>';
        }
        html += '</tbody></table>';
        if (result.nodes.length > 50) {
            html += '<p style="margin-top: 16px; color: var(--text-secondary);">Showing 50 of ' + result.nodes.length + '</p>';
        }
    } else {
        html += '<p style="color: var(--text-secondary);">No results</p>';
    }
    html += '</div></div>';

    document.getElementById('results-container').innerHTML = html;
}

/**
 * Detect CoinJoin transaction
 */
export async function detectCoinJoin() {
    const txid = document.getElementById('txid-input').value.trim();
    if (!txid) {
        alert('Please enter a transaction ID');
        return;
    }
    showLoading();
    try {
        const r = await apiCall('/analysis/coinjoin/' + txid);
        renderCJ(r);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render CoinJoin detection results
 * @param {Object} r - CoinJoin analysis data
 */
function renderCJ(r) {
    const bc = r.score > 0.7 ? 'high' : (r.score > 0.3 ? 'medium' : 'low');
    const sc = bc === 'high' ? 'poor' : (bc === 'medium' ? 'moderate' : 'good');
    let html = '<div class="card"><div class="card-header"><div class="card-title">🔀 CoinJoin Analysis</div>';
    html += '<span class="cj-badge ' + bc + '">' + (r.is_coinjoin ? 'CoinJoin Detected' : 'Not CoinJoin') + '</span></div><div class="card-body">';
    html += '<div class="privacy-score"><div class="score-circle ' + sc + '">' + (r.score * 100).toFixed(0) + '%</div>';
    html += '<div class="score-details"><div class="score-rating">' + (r.protocol || 'No CoinJoin') + '</div>';
    html += '<div class="score-summary">Confidence: ' + (r.confidence * 100).toFixed(0) + '%</div></div></div>';
    html += '<h3 style="margin-top: 24px; margin-bottom: 12px;">Stats</h3><div class="tx-details">';
    html += '<div class="tx-row"><span class="tx-label">Inputs</span><span class="tx-value">' + (r.transaction_stats ? r.transaction_stats.input_count : 'N/A') + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Outputs</span><span class="tx-value">' + (r.transaction_stats ? r.transaction_stats.output_count : 'N/A') + '</span></div>';
    html += '</div>';
    if (r.heuristics_matched && r.heuristics_matched.length > 0) {
        html += '<h3 style="margin-top: 24px; margin-bottom: 12px;">✓ Matched</h3><ul class="factor-list">';
        for (var i = 0; i < r.heuristics_matched.length; i++) {
            html += '<li class="factor-item"><span class="factor-impact positive">✓</span>' + r.heuristics_matched[i] + '</li>';
        }
        html += '</ul>';
    }
    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;
}

/**
 * Calculate privacy score for transaction/UTXO
 */
export async function calculatePrivacy() {
    const txid = document.getElementById('txid-input').value.trim();
    const vout = document.getElementById('vout-input').value;
    if (!txid) {
        alert('Please enter a transaction ID');
        return;
    }
    showLoading();
    try {
        const r = await apiCall('/analysis/privacy-score', { txid: txid, vout: vout });
        renderPrivacy(r);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render privacy score results
 * @param {Object} r - Privacy score data
 */
function renderPrivacy(r) {
    const sc = r.rating === 'good' ? 'good' : (r.rating === 'moderate' ? 'moderate' : 'poor');
    let html = '<div class="card"><div class="card-header"><div class="card-title">🛡️ Privacy Score</div></div><div class="card-body">';
    html += '<div class="privacy-score"><div class="score-circle ' + sc + '">' + r.score + '</div>';
    html += '<div class="score-details"><div class="score-rating">' + r.rating + ' Privacy</div><div class="score-summary">' + r.summary + '</div></div></div>';
    if (r.factors && r.factors.length > 0) {
        html += '<h3 style="margin-top: 24px; margin-bottom: 12px;">Factors</h3><ul class="factor-list">';
        for (var i = 0; i < r.factors.length; i++) {
            var impactClass = r.factors[i].impact.charAt(0) === '+' ? 'positive' : 'negative';
            html += '<li class="factor-item"><span class="factor-impact ' + impactClass + '">' + r.factors[i].impact + '</span>' + r.factors[i].description + '</li>';
        }
        html += '</ul>';
    }
    if (r.recommendations && r.recommendations.length > 0) {
        html += '<h3 style="margin-top: 24px; margin-bottom: 12px;">💡 Recommendations</h3><ul style="list-style: disc; margin-left: 20px; color: var(--text-secondary);">';
        for (var j = 0; j < r.recommendations.length; j++) {
            html += '<li style="padding: 4px 0;">' + r.recommendations[j] + '</li>';
        }
        html += '</ul>';
    }
    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;
}

/**
 * Get current trace data for visualization
 */
export function getCurrentTraceData() {
    return currentTraceData;
}
