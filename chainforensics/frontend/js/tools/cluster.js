/**
 * Cluster Detection Tool
 * Identifies addresses linked through common input ownership
 */

import { apiCall } from '../api.js';
import { showLoading, showError } from '../ui.js';
import { createTruncatedValue } from '../utils.js';

// State variables for advanced analysis
let currentBasicResult = null;
let currentAddress = null;

/**
 * Run cluster detection analysis
 */
export async function detectCluster() {
    const address = document.getElementById('cluster-address').value.trim();
    if (!address) {
        alert('Please enter a Bitcoin address');
        return;
    }
    const depth = document.getElementById('cluster-depth').value;
    showLoading();
    try {
        const result = await apiCall('/privacy/cluster/' + address, { max_depth: depth });

        // Store for advanced analysis
        currentBasicResult = result;
        currentAddress = address;

        renderClusterResult(result);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render cluster detection results
 * @param {Object} r - API response data
 */
function renderClusterResult(r) {
    let html = '<div class="card"><div class="card-header"><div class="card-title">🔗 Cluster Detection Results</div>';

    // Risk badge
    const riskColors = { low: 'low', medium: 'medium', high: 'high', critical: 'high' };
    const riskLabels = { low: '✓ Low Risk', medium: '⚠ Medium Risk', high: '⚠ High Risk', critical: '🚨 Critical' };
    html += '<span class="cj-badge ' + (riskColors[r.risk_level] || 'medium') + '">' + (riskLabels[r.risk_level] || r.risk_level) + '</span>';
    html += '</div><div class="card-body">';

    // Summary stats
    html += '<div class="stats-grid" style="margin-bottom: 24px;">';
    html += '<div class="stat-card"><div class="stat-value" style="color: var(--accent-purple);">' + r.cluster_size + '</div><div class="stat-label">Linked Addresses <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total number of addresses that can be attributed to the same entity through common input analysis.</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (r.total_value_btc ? r.total_value_btc.toFixed(8) : '0') + '</div><div class="stat-label">Total BTC in Cluster <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Combined unspent balance across all addresses in this cluster.</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + r.analysis_depth + '</div><div class="stat-label">Analysis Depth <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">How many levels of transaction history were analyzed.</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + r.execution_time_ms + 'ms</div><div class="stat-label">Analysis Time</div></div>';
    html += '</div>';

    // Explanation box
    if (r.cluster_size > 1) {
        html += '<div style="background: rgba(163, 113, 247, 0.1); border: 1px solid var(--accent-purple); border-radius: 8px; padding: 16px; margin-bottom: 20px;">';
        html += '<div style="color: var(--accent-purple); font-weight: 600; margin-bottom: 8px;">⚠️ What This Means</div>';
        html += '<p style="color: var(--text-secondary); font-size: 0.875rem; margin: 0;">When you spend from multiple addresses in the same transaction, blockchain observers can link those addresses together. ';
        html += 'This cluster of <strong>' + r.cluster_size + ' addresses</strong> can all be attributed to the same owner by chain analysis firms.</p>';
        html += '</div>';
    } else {
        html += '<div style="background: rgba(34, 197, 94, 0.1); border: 1px solid var(--accent-green); border-radius: 8px; padding: 16px; margin-bottom: 20px;">';
        html += '<div style="color: var(--accent-green); font-weight: 600; margin-bottom: 8px;">✓ Good Privacy Hygiene</div>';
        html += '<p style="color: var(--text-secondary); font-size: 0.875rem; margin: 0;">No linked addresses found. This address has not been spent together with other addresses, maintaining separation of identities.</p>';
        html += '</div>';
    }

    // Linked addresses list
    if (r.linked_addresses && r.linked_addresses.length > 0) {
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">';
        html += '<h3 style="margin: 0; display: flex; align-items: center; gap: 8px;">Linked Addresses <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">These addresses were found to be linked through common input ownership - they were spent together in transactions.</span></span></h3>';
        html += '<div style="display: flex; align-items: center; gap: 8px;">';
        html += '<span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip" style="width: 360px;">(Union-Find + Graph Metrics) Includes change detection, graph density, and detailed connection mapping.</span></span>';
        html += '<button id="run-advanced-btn" style="background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue)); border: none; padding: 8px 16px; border-radius: 6px; color: white; font-weight: 600; cursor: pointer; font-size: 0.875rem; display: flex; align-items: center; gap: 6px;">🔬 Run Advanced Analysis</button>';
        html += '</div>';
        html += '</div>';
        html += '<table class="io-table"><thead><tr><th>Address</th><th>Link Type</th><th>Confidence</th><th>First Seen</th></tr></thead><tbody>';
        for (var i = 0; i < Math.min(r.linked_addresses.length, 20); i++) {
            var addr = r.linked_addresses[i];
            html += '<tr>';
            html += '<td class="mono" style="font-size: 0.75rem;">' + createTruncatedValue(addr.address, addr.address.substring(0, 12) + '...' + addr.address.slice(-6), 'cluster-addr-' + i) + '</td>';
            html += '<td><span style="background: rgba(163, 113, 247, 0.2); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">Common Input</span></td>';
            html += '<td style="color: var(--accent-purple);">' + addr.confidence + '%</td>';
            html += '<td>' + (addr.first_seen || '-') + '</td>';
            html += '</tr>';
        }
        html += '</tbody></table>';
        if (r.linked_addresses.length > 20) {
            html += '<p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 8px;">...and ' + (r.linked_addresses.length - 20) + ' more addresses</p>';
        }
    }

    // Recommendations
    if (r.recommendations && r.recommendations.length > 0) {
        html += '<div style="margin-top: 20px; background: var(--bg-secondary); border-radius: 8px; padding: 16px;">';
        html += '<div style="font-weight: 600; margin-bottom: 8px;">💡 Recommendations</div>';
        html += '<ul style="margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 0.875rem;">';
        for (var j = 0; j < r.recommendations.length; j++) {
            html += '<li style="margin-bottom: 4px;">' + r.recommendations[j] + '</li>';
        }
        html += '</ul></div>';
    }

    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;

    // Attach event listener to advanced analysis button
    const advancedBtn = document.getElementById('run-advanced-btn');
    if (advancedBtn) {
        advancedBtn.addEventListener('click', runAdvancedAnalysis);
    }
}

/**
 * Run advanced cluster analysis using Union-Find algorithm
 */
async function runAdvancedAnalysis() {
    if (!currentAddress) {
        alert('No address to analyze');
        return;
    }

    const depth = document.getElementById('cluster-depth').value;
    showLoading();

    try {
        const result = await apiCall('/privacy/cluster/' + currentAddress + '/advanced', {
            max_depth: depth,
            include_change_heuristic: true,
            min_confidence: 0.5
        });
        renderAdvancedClusterResult(result, currentBasicResult);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render advanced cluster detection results
 * @param {Object} r - Advanced API response data
 * @param {Object} basic - Basic cluster result for comparison
 */
function renderAdvancedClusterResult(r, basic) {
    let html = '<div class="card"><div class="card-header"><div class="card-title">🔬 Advanced Cluster Analysis</div>';

    // Risk badge
    const riskColors = { low: 'low', medium: 'medium', high: 'high', critical: 'high' };
    const riskLabels = { low: '✓ Low Risk', medium: '⚠ Medium Risk', high: '⚠ High Risk', critical: '🚨 Critical' };
    html += '<span class="cj-badge ' + (riskColors[r.risk_level] || 'medium') + '">' + (riskLabels[r.risk_level] || r.risk_level) + '</span>';
    html += '</div><div class="card-body">';

    // Comparison banner if we found more addresses
    if (basic && r.cluster_size > basic.cluster_size) {
        const delta = r.cluster_size - basic.cluster_size;
        html += '<div style="background: linear-gradient(135deg, rgba(163, 113, 247, 0.1), rgba(59, 130, 246, 0.1)); border: 1px solid var(--accent-purple); border-radius: 8px; padding: 16px; margin-bottom: 20px;">';
        html += '<div style="color: var(--accent-purple); font-weight: 600; margin-bottom: 8px;">🔍 Advanced Analysis Found ' + delta + ' Additional Address(es)</div>';
        html += '<p style="color: var(--text-secondary); font-size: 0.875rem; margin: 0;">Union-Find algorithm with change detection discovered addresses not found in basic analysis.</p>';
        html += '</div>';
    }

    // Summary stats
    html += '<div class="stats-grid" style="margin-bottom: 24px;">';
    html += '<div class="stat-card"><div class="stat-value" style="color: var(--accent-purple);">' + r.cluster_size + '</div><div class="stat-label">Cluster Size <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Number of addresses linked together through transaction history</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (r.total_value_btc ? r.total_value_btc.toFixed(8) : '0') + '</div><div class="stat-label">Total BTC</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + r.graph_metrics.edge_count + '</div><div class="stat-label">Connections (Edges) <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total transaction connections between addresses in the cluster</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (r.graph_metrics.graph_density * 100).toFixed(1) + '%</div><div class="stat-label">Graph Density <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">How interconnected the cluster is (0-100%). Higher = more connections</span></span></div></div>';
    html += '</div>';

    // Heuristic breakdown
    html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px; margin-bottom: 20px;">';
    html += '<div style="font-weight: 600; margin-bottom: 12px;">📊 Heuristic Breakdown</div>';
    html += '<div style="display: flex; gap: 16px;">';
    html += '<div style="flex: 1;"><div style="color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 4px;">Common Input <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Addresses spent together in the same transaction (strong ownership signal)</span></span></div><div style="font-size: 1.5rem; font-weight: 600; color: var(--accent-purple);">' + r.heuristic_breakdown.common_input + '</div></div>';
    html += '<div style="flex: 1;"><div style="color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 4px;">Change Detection <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Addresses identified as likely change outputs returning to sender</span></span></div><div style="font-size: 1.5rem; font-weight: 600; color: var(--accent-blue);">' + r.heuristic_breakdown.change_heuristic + '</div></div>';
    html += '<div style="flex: 1;"><div style="color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 4px;">Avg Degree <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Average number of connections per address</span></span></div><div style="font-size: 1.5rem; font-weight: 600;">' + r.graph_metrics.average_degree + '</div></div>';
    html += '</div></div>';

    // Graph metrics explanation
    html += '<div style="background: rgba(59, 130, 246, 0.1); border: 1px solid var(--accent-blue); border-radius: 8px; padding: 16px; margin-bottom: 20px;">';
    html += '<div style="color: var(--accent-blue); font-weight: 600; margin-bottom: 8px;">📈 Graph Analysis</div>';
    html += '<p style="color: var(--text-secondary); font-size: 0.875rem; margin: 0 0 8px 0;"><strong>Graph Density:</strong> ' + (r.graph_metrics.graph_density * 100).toFixed(1) + '% of all possible connections exist. ';
    if (r.graph_metrics.graph_density > 0.7) {
        html += 'HIGH density indicates frequent address reuse.';
    } else if (r.graph_metrics.graph_density > 0.3) {
        html += 'MODERATE density - some address reuse detected.';
    } else {
        html += 'LOW density - relatively good separation.';
    }
    html += '</p>';
    html += '<p style="color: var(--text-secondary); font-size: 0.875rem; margin: 0;"><strong>Average Degree:</strong> Each address is connected to ' + r.graph_metrics.average_degree + ' other addresses on average.</p>';
    html += '</div>';

    // Cluster members table
    if (r.cluster_members && r.cluster_members.length > 0) {
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">';
        html += '<h3 style="margin: 0;">Cluster Members (' + r.cluster_members.length + ' shown)</h3>';
        html += '<button id="back-to-basic-btn-top" style="background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue)); border: none; padding: 8px 16px; border-radius: 6px; color: white; font-weight: 600; cursor: pointer; font-size: 0.875rem;">← Back to Basic Analysis</button>';
        html += '</div>';
        html += '<table class="io-table"><thead><tr><th>Address</th><th>First Seen</th><th>Tx Count</th><th>UTXO Value</th></tr></thead><tbody>';
        for (var i = 0; i < Math.min(r.cluster_members.length, 20); i++) {
            var member = r.cluster_members[i];
            html += '<tr>';
            html += '<td class="mono" style="font-size: 0.75rem;">' + createTruncatedValue(member.address, member.address.substring(0, 12) + '...' + member.address.slice(-6), 'adv-member-' + i) + '</td>';
            html += '<td>' + (member.first_seen || '-') + '</td>';
            html += '<td>' + member.tx_count + '</td>';
            html += '<td>' + (member.utxo_value_sats / 100000000).toFixed(8) + ' BTC</td>';
            html += '</tr>';
        }
        html += '</tbody></table>';
        if (r.cluster_members.length > 20) {
            html += '<p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 8px;">...and ' + (r.cluster_members.length - 20) + ' more addresses</p>';
        }
    }

    // Edges (connections) table
    if (r.edges && r.edges.length > 0) {
        html += '<h3 style="margin-top: 24px; margin-bottom: 12px;">Address Connections (' + r.edges.length + ' edges)</h3>';
        html += '<table class="io-table"><thead><tr><th>From</th><th>To</th><th>Type</th><th>Confidence</th></tr></thead><tbody>';
        for (var i = 0; i < Math.min(r.edges.length, 15); i++) {
            var edge = r.edges[i];
            var typeColor = edge.type === 'common_input' ? 'var(--accent-purple)' : 'var(--accent-blue)';
            var typeLabel = edge.type === 'common_input' ? 'Common Input' : 'Change Detection';
            html += '<tr>';
            html += '<td class="mono" style="font-size: 0.7rem;">' + createTruncatedValue(edge.from, edge.from.substring(0, 10) + '...', 'edge-from-' + i) + '</td>';
            html += '<td class="mono" style="font-size: 0.7rem;">' + createTruncatedValue(edge.to, edge.to.substring(0, 10) + '...', 'edge-to-' + i) + '</td>';
            html += '<td><span style="background: rgba(163, 113, 247, 0.2); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; color: ' + typeColor + ';">' + typeLabel + '</span></td>';
            html += '<td style="color: ' + typeColor + ';">' + (edge.confidence * 100).toFixed(0) + '%</td>';
            html += '</tr>';
        }
        html += '</tbody></table>';
        if (r.edges.length > 15) {
            html += '<p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 8px;">...and ' + (r.edges.length - 15) + ' more connections</p>';
        }
    }

    // Recommendations
    if (r.recommendations && r.recommendations.length > 0) {
        html += '<div style="margin-top: 20px; background: var(--bg-secondary); border-radius: 8px; padding: 16px;">';
        html += '<div style="font-weight: 600; margin-bottom: 8px;">💡 Enhanced Recommendations</div>';
        html += '<ul style="margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 0.875rem;">';
        for (var j = 0; j < r.recommendations.length; j++) {
            html += '<li style="margin-bottom: 4px;">' + r.recommendations[j] + '</li>';
        }
        html += '</ul></div>';
    }

    // Back button
    html += '<div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--border-color);">';
    html += '<button id="back-to-basic-btn-bottom" class="button" style="width: 100%;">⬅ Back to Basic Analysis</button>';
    html += '</div>';

    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;

    // Attach event listeners to back buttons
    const backBtnTop = document.getElementById('back-to-basic-btn-top');
    const backBtnBottom = document.getElementById('back-to-basic-btn-bottom');

    if (backBtnTop) {
        backBtnTop.addEventListener('click', () => {
            if (currentBasicResult) {
                renderClusterResult(currentBasicResult);
            }
        });
    }

    if (backBtnBottom) {
        backBtnBottom.addEventListener('click', () => {
            if (currentBasicResult) {
                renderClusterResult(currentBasicResult);
            }
        });
    }
}

// Export functions for use in HTML
if (typeof window !== 'undefined') {
    window.clusterModule = {
        detectCluster,
        runAdvancedAnalysis,
        renderClusterResult,
        renderAdvancedClusterResult
    };
}
