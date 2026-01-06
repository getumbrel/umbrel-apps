/**
 * Address Lookup Tool
 * Address validation, balance lookup, dust attack detection, and labeling
 */

import { apiCall } from '../api.js';
import { showLoading, showError } from '../ui.js';
import { createTruncatedValue } from '../utils.js';

/**
 * Validate Bitcoin address
 */
export async function validateAddress() {
    const addr = document.getElementById('address-input').value.trim();
    if (!addr) {
        alert('Please enter a Bitcoin address');
        return;
    }
    showLoading();
    try {
        const r = await apiCall('/addresses/' + addr + '/validate');
        renderAddrVal(r);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render address validation results
 * @param {Object} r - Validation data
 */
function renderAddrVal(r) {
    let html = '<div class="card"><div class="card-header"><div class="card-title">🔍 Address Validation</div>';
    html += '<span class="cj-badge ' + (r.is_valid ? 'low' : 'high') + '">' + (r.is_valid ? '✓ Valid' : '✗ Invalid') + '</span></div><div class="card-body"><div class="tx-details">';
    html += '<div class="tx-row"><span class="tx-label">Address</span><span class="tx-value">' + r.address + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Type</span><span class="tx-value">' + r.type + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Network</span><span class="tx-value">' + r.network + '</span></div>';
    if (r.is_witness !== undefined) {
        html += '<div class="tx-row"><span class="tx-label">SegWit</span><span class="tx-value">' + (r.is_witness ? 'Yes' : 'No') + '</span></div>';
    }
    html += '</div></div></div>';
    document.getElementById('results-container').innerHTML = html;
}

/**
 * Get address information (balance, UTXOs, transactions)
 */
export async function getAddressInfo() {
    const addr = document.getElementById('address-input').value.trim();
    if (!addr) {
        alert('Please enter a Bitcoin address');
        return;
    }
    showLoading();
    try {
        const r = await apiCall('/addresses/' + addr + '/info');
        renderAddrInfo(r);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Get category color
 * @param {string} category - Category name
 * @returns {string} CSS color value
 */
function getCategoryColor(category) {
    const colors = {
        'personal': 'var(--accent-blue)',
        'exchange': 'var(--accent-purple)',
        'merchant': 'var(--accent-green)',
        'mixer': 'var(--accent-orange)',
        'other': 'var(--text-secondary)'
    };
    return colors[category] || colors['other'];
}

/**
 * Get category badge HTML
 * @param {string} category - Category name
 * @returns {string} Badge HTML
 */
function getCategoryBadge(category) {
    const color = getCategoryColor(category);
    const label = category.charAt(0).toUpperCase() + category.slice(1);
    return '<span style="background: ' + color + '; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px;">' + label + '</span>';
}

/**
 * Render address information
 * @param {Object} r - Address info data
 */
function renderAddrInfo(r) {
    const bal = r.balance || {};
    const utxos = r.utxos || [];
    const txs = r.transactions || [];
    const warnings = r.warnings || [];
    const label = r.label || null;

    let html = '<div class="card"><div class="card-header"><div class="card-title">💰 Address Info</div>';
    html += '<span class="cj-badge ' + (r.fulcrum_status === 'connected' ? 'low' : 'medium') + '">Fulcrum: ' + r.fulcrum_status + '</span></div><div class="card-body">';

    // Display label if it exists
    if (label) {
        html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 12px; margin-bottom: 16px;">';
        html += '<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">';
        html += '<span style="font-size: 1.1rem;">📝 ' + escapeHtml(label.label) + '</span>';
        html += getCategoryBadge(label.category);
        html += '</div>';
        if (label.notes) {
            html += '<div style="color: var(--text-secondary); font-size: 0.875rem;">' + escapeHtml(label.notes) + '</div>';
        }
        html += '</div>';
    }

    // Show warnings if any
    if (warnings.length > 0) {
        html += '<div style="background: rgba(210, 153, 34, 0.1); border: 1px solid var(--accent-orange); border-radius: 8px; padding: 12px; margin-bottom: 16px;">';
        html += '<div style="color: var(--accent-orange); font-weight: 600; margin-bottom: 8px;">⚠️ Warnings</div>';
        html += '<ul style="margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 0.875rem;">';
        for (var w = 0; w < warnings.length; w++) {
            html += '<li>' + warnings[w] + '</li>';
        }
        html += '</ul></div>';
    }

    if (r.balance) {
        html += '<div class="address-balance"><div><div class="balance-amount">' + (bal.total_btc ? bal.total_btc.toFixed(8) : '0') + ' BTC</div>';
        html += '<div class="balance-label">Total Balance</div></div>';
        html += '<div style="margin-left: 40px;"><div style="color: var(--accent-green);">✓ ' + (bal.confirmed_btc ? bal.confirmed_btc.toFixed(8) : '0') + ' confirmed</div>';
        html += '<div style="color: var(--accent-orange);">⏳ ' + (bal.unconfirmed_btc ? bal.unconfirmed_btc.toFixed(8) : '0') + ' unconfirmed</div></div></div>';

        // First row of stats
        html += '<div class="stats-grid" style="margin-bottom: 12px;">';
        html += '<div class="stat-card"><div class="stat-value">' + (r.transaction_count || 0) + '</div><div class="stat-label">Transactions <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total number of transactions involving this address (both incoming and outgoing).</span></span></div></div>';
        html += '<div class="stat-card"><div class="stat-value">' + (r.utxo_count || 0) + '</div><div class="stat-label">UTXOs <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Unspent Transaction Outputs - the number of separate coin holdings at this address.</span></span></div></div>';
        html += '<div class="stat-card"><div class="stat-value">' + (r.first_seen_height || '-') + '</div><div class="stat-label">First Seen <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Block height of the first transaction involving this address.</span></span></div></div>';
        html += '<div class="stat-card"><div class="stat-value">' + (r.last_seen_height || '-') + '</div><div class="stat-label">Last Seen <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Block height of the most recent transaction involving this address.</span></span></div></div>';
        html += '</div>';

        // Second row of stats - Total Received, Total Sent, Total Volume
        var totalReceived = r.total_received_btc != null ? r.total_received_btc.toFixed(8) : '-';
        var totalSent = r.total_sent_btc != null ? r.total_sent_btc.toFixed(8) : '-';
        var totalVolume = (r.total_received_btc != null && r.total_sent_btc != null) ?
            (r.total_received_btc + r.total_sent_btc).toFixed(8) : '-';
        var totalsNote = r.totals_complete === false ? ' <span style="color: var(--accent-orange); font-size: 0.6rem;">*partial</span>' : '';

        html += '<div class="stats-grid" style="margin-bottom: 24px;">';
        html += '<div class="stat-card"><div class="stat-value" style="color: var(--accent-green);">' + totalReceived + '</div><div class="stat-label">Total Received' + totalsNote + ' <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total BTC received by this address over time. Sum of all incoming transaction outputs.</span></span></div></div>';
        html += '<div class="stat-card"><div class="stat-value" style="color: var(--accent-red);">' + totalSent + '</div><div class="stat-label">Total Sent' + totalsNote + ' <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total BTC sent from this address over time. Sum of all spent transaction inputs.</span></span></div></div>';
        html += '<div class="stat-card"><div class="stat-value" style="color: var(--accent-purple);">' + totalVolume + '</div><div class="stat-label">Total Volume' + totalsNote + ' <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total volume of BTC moved through this address (received + sent).</span></span></div></div>';
        html += '</div>';
    } else {
        html += '<p style="color: var(--text-secondary);">Fulcrum not available.</p>';
    }

    if (utxos.length > 0) {
        var utxoTitle = 'UTXOs (' + utxos.length + ')';
        if (r.utxos_truncated) {
            utxoTitle += ' <span style="color: var(--accent-orange); font-size: 0.75rem;">- showing first ' + utxos.length + '</span>';
        }
        html += '<h3 style="margin-bottom: 12px;">' + utxoTitle + '</h3><div class="utxo-list">';
        var showUtxos = utxos.slice(0, 20);
        for (var i = 0; i < showUtxos.length; i++) {
            var u = showUtxos[i];
            html += '<div class="utxo-item"><div><div class="utxo-txid">' + createTruncatedValue(u.txid, u.txid.substring(0, 16) + '...', 'addr-utxo-' + i) + '#' + u.vout + '</div>';
            html += '<div style="font-size: 0.75rem; color: var(--text-secondary);">' + (u.is_confirmed ? 'Block ' + u.height : 'Unconfirmed') + '</div></div>';
            html += '<div class="utxo-value">' + u.value_btc.toFixed(8) + ' BTC</div></div>';
        }
        if (utxos.length > 20) {
            html += '<p style="text-align: center; color: var(--text-secondary);">...and ' + (utxos.length - 20) + ' more</p>';
        }
        html += '</div>';
    }

    if (txs.length > 0) {
        var txTitle = 'Recent Transactions';
        if (r.history_truncated) {
            txTitle += ' <span style="color: var(--accent-orange); font-size: 0.75rem;">- showing last ' + txs.length + ' of ' + (r.transaction_count || 'many') + '</span>';
        }
        html += '<h3 style="margin-top: 24px; margin-bottom: 12px;">' + txTitle + '</h3>';
        html += '<table class="io-table"><thead><tr><th>TXID</th><th>Height</th><th>Status</th></tr></thead><tbody>';
        var showTxs = txs.slice(0, 10);
        for (var j = 0; j < showTxs.length; j++) {
            var t = showTxs[j];
            html += '<tr><td class="mono">' + createTruncatedValue(t.txid, t.txid.substring(0, 20) + '...', 'addr-tx-' + j) + '</td>';
            html += '<td>' + (t.height || 'Mempool') + '</td><td>' + (t.is_confirmed ? '✓' : '⏳') + '</td></tr>';
        }
        html += '</tbody></table>';
    }

    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Check for dust attacks
 */
export async function checkDustAttack() {
    const addr = document.getElementById('address-input').value.trim();
    if (!addr) {
        alert('Please enter a Bitcoin address');
        return;
    }
    showLoading();
    try {
        const r = await apiCall('/addresses/' + addr + '/dust-check');
        renderDust(r);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render dust attack check results
 * @param {Object} r - Dust check data
 */
function renderDust(r) {
    let html = '<div class="card"><div class="card-header"><div class="card-title">🔬 Dust Attack Check</div></div><div class="card-body">';
    if (r.suspicious_count > 0) {
        html += '<div class="dust-warning"><div class="dust-warning-title">⚠️ Warning: ' + r.suspicious_count + ' Suspicious UTXO(s)</div>';
        html += '<p>' + r.recommendation + '</p></div>';
    } else {
        html += '<div style="background: rgba(35, 134, 54, 0.1); border: 1px solid var(--accent-green); border-radius: 8px; padding: 16px; margin-bottom: 16px;">';
        html += '<div style="color: var(--accent-green); font-weight: 600;">✓ No Dust Attack Detected</div>';
        html += '<p style="color: var(--text-secondary); margin-top: 8px;">' + r.recommendation + '</p></div>';
    }
    html += '<div class="stats-grid">';
    html += '<div class="stat-card"><div class="stat-value">' + r.total_utxos + '</div><div class="stat-label">Total UTXOs</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + r.dust_utxos_count + '</div><div class="stat-label">Dust UTXOs</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + r.total_dust_value_sats + '</div><div class="stat-label">Total Dust (sats)</div></div>';
    html += '</div>';
    if (r.suspicious_utxos && r.suspicious_utxos.length > 0) {
        html += '<h3 style="margin-top: 24px; margin-bottom: 12px;">⚠️ Suspicious</h3><div class="utxo-list">';
        for (var i = 0; i < r.suspicious_utxos.length; i++) {
            var u = r.suspicious_utxos[i];
            html += '<div class="utxo-item" style="border-left: 3px solid var(--accent-red);"><div>';
            html += '<div class="utxo-txid">' + u.txid.substring(0, 16) + '...#' + u.vout + '</div>';
            html += '<div style="font-size: 0.75rem; color: var(--accent-red);">' + u.warning + '</div></div>';
            html += '<div class="utxo-value" style="color: var(--accent-red);">' + u.value_sats + ' sats</div></div>';
        }
        html += '</div><p style="margin-top: 16px; color: var(--accent-orange); font-size: 0.875rem;">💡 Do NOT consolidate these with your other coins!</p>';
    }
    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;
}
