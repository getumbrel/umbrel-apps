/**
 * Visualization Module
 * Transaction flow visualization using vis.js network graphs
 */

import { getCurrentTraceData } from './tools/transaction.js';

let visNetwork = null;

/**
 * Open visualization modal
 */
export function openVisualization() {
    const currentTraceData = getCurrentTraceData();
    if (!currentTraceData || !currentTraceData.nodes || currentTraceData.nodes.length === 0) {
        alert('No trace data available. Run a trace first.');
        return;
    }

    document.getElementById('vis-modal').classList.add('active');
    document.getElementById('vis-modal-title-text').textContent =
        'Transaction Flow - ' + (currentTraceData._direction === 'forward' ? 'Forward Trace' : 'Backward Trace');

    renderVisualization();
}

/**
 * Close visualization modal
 */
export function closeVisualization() {
    document.getElementById('vis-modal').classList.remove('active');
    if (visNetwork) {
        visNetwork.destroy();
        visNetwork = null;
    }
}

/**
 * Zoom in on visualization
 */
export function visZoomIn() {
    if (visNetwork) {
        var scale = visNetwork.getScale();
        visNetwork.moveTo({ scale: scale * 1.3 });
    }
}

/**
 * Zoom out on visualization
 */
export function visZoomOut() {
    if (visNetwork) {
        var scale = visNetwork.getScale();
        visNetwork.moveTo({ scale: scale / 1.3 });
    }
}

/**
 * Fit all nodes in view
 */
export function visFitAll() {
    if (visNetwork) {
        visNetwork.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
    }
}

/**
 * Render the visualization graph
 */
function renderVisualization() {
    var data = getCurrentTraceData();
    var container = document.getElementById('vis-container');

    // Update stats
    document.getElementById('vis-stat-nodes').textContent = data.nodes.length;
    document.getElementById('vis-stat-edges').textContent = data.edges ? data.edges.length : 0;
    var maxDepth = Math.max.apply(null, data.nodes.map(function(n) { return n.depth; }));
    document.getElementById('vis-stat-depth').textContent = maxDepth;
    var totalBtc = data.nodes.reduce(function(sum, n) { return sum + (n.value_btc || 0); }, 0);
    document.getElementById('vis-stat-value').textContent = totalBtc.toFixed(2);

    // Build node lookup
    var nodeLookup = {};
    data.nodes.forEach(function(n) {
        var key = n.txid + ':' + n.vout;
        nodeLookup[key] = n;
    });

    // Create vis.js nodes
    var visNodes = [];
    var nodeIdMap = {};

    data.nodes.forEach(function(n, index) {
        var nodeKey = n.txid + ':' + n.vout;
        var nodeId = index;
        nodeIdMap[nodeKey] = nodeId;

        // Determine node color based on status and properties
        var nodeColor, borderColor, fontColor;
        var isStart = (n.txid === data.start_txid && n.vout === data.start_vout);

        if (isStart) {
            nodeColor = { background: '#388bfd', border: '#58a6ff', highlight: { background: '#58a6ff', border: '#79c0ff' } };
            borderColor = '#58a6ff';
            fontColor = '#ffffff';
        } else if (n.coinjoin_score > 0.7) {
            nodeColor = { background: '#8957e5', border: '#a371f7', highlight: { background: '#a371f7', border: '#c297ff' } };
            borderColor = '#a371f7';
            fontColor = '#ffffff';
        } else if (n.status === 'unspent') {
            nodeColor = { background: '#238636', border: '#2ea043', highlight: { background: '#2ea043', border: '#3fb950' } };
            borderColor = '#2ea043';
            fontColor = '#ffffff';
        } else if (n.status === 'coinbase') {
            nodeColor = { background: '#9e6a03', border: '#d29922', highlight: { background: '#d29922', border: '#f0b429' } };
            borderColor = '#d29922';
            fontColor = '#ffffff';
        } else {
            nodeColor = { background: '#484f58', border: '#6e7681', highlight: { background: '#6e7681', border: '#8b949e' } };
            borderColor = '#6e7681';
            fontColor = '#c9d1d9';
        }

        // Node size based on value (log scale)
        var baseSize = 25;
        var valueSize = n.value_btc ? Math.log10(n.value_btc + 1) * 10 : 0;
        var size = Math.max(baseSize, Math.min(baseSize + valueSize, 60));

        // Node label
        var label;
        if (n.address) {
            label = n.address.substring(0, 8) + '...';
        } else if (n.script_type === 'pubkey') {
            label = 'P2PK';
        } else if (n.script_type === 'nulldata' || n.script_type === 'op_return') {
            label = 'OP_RETURN';
        } else {
            label = 'Unknown';
        }
        if (isStart) label = '★ ' + label;

        visNodes.push({
            id: nodeId,
            label: label,
            title: createNodeTooltip(n, isStart),
            size: size,
            color: nodeColor,
            borderWidth: isStart ? 3 : 2,
            borderWidthSelected: 4,
            font: { color: fontColor, size: 11, face: 'SF Mono, Monaco, monospace' },
            shadow: { enabled: true, color: 'rgba(0,0,0,0.3)', size: 8, x: 2, y: 2 },
            _nodeData: n
        });
    });

    // Create vis.js edges
    var visEdges = [];
    if (data.edges) {
        data.edges.forEach(function(e, index) {
            var fromKey = e.from_txid + ':' + e.from_vout;
            var fromId = nodeIdMap[fromKey];

            // Find destination node
            var toId = null;
            for (var key in nodeIdMap) {
                if (key.startsWith(e.to_txid + ':')) {
                    toId = nodeIdMap[key];
                    break;
                }
            }

            if (fromId !== undefined && toId !== undefined) {
                var valueBtc = e.value_sats / 100000000;
                visEdges.push({
                    id: index,
                    from: fromId,
                    to: toId,
                    arrows: { to: { enabled: true, scaleFactor: 0.7, type: 'arrow' } },
                    color: { color: '#30363d', highlight: '#58a6ff', hover: '#6e7681' },
                    width: Math.max(1, Math.min(Math.log10(valueBtc + 1) * 2, 6)),
                    smooth: { enabled: true, type: 'curvedCW', roundness: 0.15 },
                    title: valueBtc.toFixed(8) + ' BTC',
                    font: { color: '#8b949e', size: 9, strokeWidth: 0, background: '#0d1117' }
                });
            }
        });
    }

    // Vis.js configuration
    var options = {
        nodes: {
            shape: 'dot',
            scaling: { min: 20, max: 60 }
        },
        edges: {
            selectionWidth: 2
        },
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -50,
                centralGravity: 0.01,
                springLength: 120,
                springConstant: 0.08,
                damping: 0.4,
                avoidOverlap: 0.5
            },
            stabilization: {
                enabled: true,
                iterations: 200,
                updateInterval: 25
            }
        },
        layout: {
            hierarchical: {
                enabled: true,
                direction: data._direction === 'forward' ? 'LR' : 'RL',
                sortMethod: 'directed',
                levelSeparation: 180,
                nodeSpacing: 100,
                treeSpacing: 120,
                blockShifting: true,
                edgeMinimization: true,
                parentCentralization: true
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 100,
            hideEdgesOnDrag: true,
            navigationButtons: false,
            keyboard: {
                enabled: true,
                speed: { x: 10, y: 10, zoom: 0.05 }
            }
        }
    };

    // Create network
    var networkData = { nodes: new vis.DataSet(visNodes), edges: new vis.DataSet(visEdges) };
    visNetwork = new vis.Network(container, networkData, options);

    // Event: node click
    visNetwork.on('click', function(params) {
        if (params.nodes.length > 0) {
            var nodeId = params.nodes[0];
            var node = visNodes.find(function(n) { return n.id === nodeId; });
            if (node && node._nodeData) {
                showNodeDetails(node._nodeData);
            }
        }
    });

    // Fit after stabilization
    visNetwork.once('stabilizationIterationsDone', function() {
        visNetwork.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
    });
}

/**
 * Create tooltip for node hover
 * @param {Object} n - Node data
 * @param {boolean} isStart - Whether this is the starting node
 * @returns {string} HTML tooltip
 */
function createNodeTooltip(n, isStart) {
    var html = '<div style="background: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d; max-width: 280px;">';
    if (isStart) html += '<div style="color: #58a6ff; font-weight: bold; margin-bottom: 8px;">★ Starting Point</div>';
    html += '<div style="color: #8b949e; font-size: 11px;">TXID</div>';
    html += '<div style="color: #c9d1d9; font-family: monospace; font-size: 10px; word-break: break-all; margin-bottom: 8px;">' + n.txid + '</div>';
    html += '<div style="color: #8b949e; font-size: 11px;">Address</div>';
    var addrTooltip;
    if (n.address) {
        addrTooltip = n.address;
    } else if (n.script_type === 'pubkey') {
        addrTooltip = '<span style="color: #d29922;">P2PK (Pay-to-Public-Key)</span><br><span style="color: #8b949e; font-size: 9px;">Early Bitcoin format - no address</span>';
    } else if (n.script_type === 'nulldata' || n.script_type === 'op_return') {
        addrTooltip = '<span style="color: #8b949e;">OP_RETURN (data output)</span>';
    } else {
        addrTooltip = 'Unknown';
    }
    html += '<div style="color: #c9d1d9; font-family: monospace; font-size: 10px; word-break: break-all; margin-bottom: 8px;">' + addrTooltip + '</div>';
    html += '<div style="display: flex; gap: 16px;">';
    html += '<div><span style="color: #8b949e; font-size: 11px;">Value</span><div style="color: #58a6ff; font-weight: bold;">' + (n.value_btc ? n.value_btc.toFixed(8) : '?') + ' BTC</div></div>';
    html += '<div><span style="color: #8b949e; font-size: 11px;">Depth</span><div style="color: #c9d1d9; font-weight: bold;">' + n.depth + '</div></div>';
    html += '</div>';
    html += '</div>';
    return html;
}

/**
 * Show node details in sidebar
 * @param {Object} n - Node data
 */
function showNodeDetails(n) {
    var html = '<div class="vis-node-details-title">📍 Node Details</div>';
    html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">TXID</span><span class="vis-node-detail-value">' + n.txid.substring(0, 16) + '...</span></div>';

    // Format date
    var dateDetail = '-';
    if (n.block_time) {
        var d = new Date(n.block_time);
        dateDetail = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) + ' ' + d.toLocaleTimeString();
    }
    html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">Date</span><span class="vis-node-detail-value">' + dateDetail + '</span></div>';

    html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">Depth</span><span class="vis-node-detail-value">' + n.depth + '</span></div>';
    html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">Output Index</span><span class="vis-node-detail-value">' + n.vout + '</span></div>';

    var addrDetail;
    if (n.address) {
        addrDetail = n.address.substring(0, 16) + '...';
    } else if (n.script_type === 'pubkey') {
        addrDetail = '<span style="color: var(--accent-orange);">P2PK (Raw Pubkey)</span>';
    } else if (n.script_type === 'nulldata' || n.script_type === 'op_return') {
        addrDetail = '<span style="color: var(--text-secondary);">OP_RETURN</span>';
    } else {
        addrDetail = '-';
    }
    html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">Address</span><span class="vis-node-detail-value">' + addrDetail + '</span></div>';
    html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">Script Type</span><span class="vis-node-detail-value">' + (n.script_type || '-') + '</span></div>';
    html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">Value</span><span class="vis-node-detail-value" style="color: var(--accent-blue);">' + (n.value_btc ? n.value_btc.toFixed(8) : '?') + ' BTC</span></div>';
    html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">Status</span><span class="vis-node-detail-value">' + n.status + '</span></div>';
    if (n.coinjoin_score > 0) {
        html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">CoinJoin Score</span><span class="vis-node-detail-value" style="color: var(--accent-purple);">' + (n.coinjoin_score * 100).toFixed(0) + '%</span></div>';
    }
    if (n.block_height) {
        html += '<div class="vis-node-detail-row"><span class="vis-node-detail-label">Block Height</span><span class="vis-node-detail-value">' + n.block_height + '</span></div>';
    }
    document.getElementById('vis-node-details').innerHTML = html;
}

/**
 * Initialize visualization modal event listeners
 */
export function initVisualizationModal() {
    // Close modal on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeVisualization();
        }
    });

    // Close modal on background click
    document.getElementById('vis-modal').addEventListener('click', function(e) {
        if (e.target.id === 'vis-modal') closeVisualization();
    });
}
