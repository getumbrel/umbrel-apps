/**
 * UTXO Privacy Rating Tool
 * Rates individual UTXOs based on privacy factors
 */

import { apiCall } from '../api.js';
import { showLoading, showError, initTooltips } from '../ui.js';
import { createTruncatedValue } from '../utils.js';

// State variables for advanced analysis
let currentBasicResult = null;
let currentAddress = null;
let currentSelectedUtxo = null;

/**
 * Run UTXO privacy analysis
 */
export async function analyzeUTXOPrivacy() {
    const address = document.getElementById('utxo-privacy-address').value.trim();
    if (!address) {
        alert('Please enter a Bitcoin address');
        return;
    }
    showLoading();
    try {
        const result = await apiCall('/privacy/utxo-rating/' + address);
        currentBasicResult = result;
        currentAddress = address;

        // Skip basic results, go directly to UTXO selector
        showUtxoSelector();
    } catch (e) {
        showError(e.message);
    }
}


/**
 * Show UTXO selector modal for privacy analysis
 */
function showUtxoSelector() {
    if (!currentBasicResult || !currentBasicResult.utxos || currentBasicResult.utxos.length === 0) {
        alert('No UTXOs available for analysis');
        return;
    }

    let html = '<div class="card"><div class="card-header"><div class="card-title">🔬 UTXO Privacy Analysis</div></div><div class="card-body">';
    html += '<p style="margin-bottom: 20px; color: var(--text-secondary);">Select a UTXO to perform in-depth privacy analysis including temporal correlation, value fingerprinting, wallet fingerprinting, peeling chain detection, and attack vector assessment.</p>';
    html += '<div style="background: rgba(210, 153, 34, 0.1); border: 1px solid var(--accent-orange); border-radius: 8px; padding: 12px; margin-bottom: 20px;">';
    html += '<div style="color: var(--accent-orange); font-weight: 600; margin-bottom: 4px;">⏱ Analysis Time: 8-15 seconds</div>';
    html += '<p style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;">This analysis performs deep blockchain tracing with sophisticated heuristics.</p>';
    html += '</div>';

    // UTXO selection list
    html += '<div style="max-height: 400px; overflow-y: auto;">';
    for (var i = 0; i < currentBasicResult.utxos.length; i++) {
        var utxo = currentBasicResult.utxos[i];
        var ratingIcon = utxo.rating === 'red' ? '🔴' : (utxo.rating === 'yellow' ? '🟡' : '🟢');
        var ratingBg = utxo.rating === 'red' ? 'rgba(239, 68, 68, 0.1)' : (utxo.rating === 'yellow' ? 'rgba(210, 153, 34, 0.1)' : 'rgba(34, 197, 94, 0.1)');
        var ratingBorder = utxo.rating === 'red' ? 'var(--accent-red)' : (utxo.rating === 'yellow' ? 'var(--accent-orange)' : 'var(--accent-green)');

        html += '<div style="background: ' + ratingBg + '; border: 1px solid ' + ratingBorder + '; border-radius: 8px; padding: 12px; margin-bottom: 8px; cursor: pointer; transition: all 0.2s;" class="utxo-selector-item" data-txid="' + utxo.txid + '" data-vout="' + utxo.vout + '">';
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">';
        html += '<div style="display: flex; align-items: center; gap: 8px;"><span style="font-size: 1.25rem;">' + ratingIcon + '</span>';
        var utxoIdentifier = utxo.txid + ':' + utxo.vout;
        html += '<span style="font-size: 0.8rem;">UTXO: </span><span class="mono" style="font-size: 0.8rem;">' + createTruncatedValue(utxoIdentifier, utxo.txid.substring(0, 12) + '...:' + utxo.vout, 'selector-' + i) + '</span></div>';
        html += '<div style="font-weight: 600;">' + utxo.value_btc.toFixed(8) + ' BTC</div>';
        html += '</div>';
        html += '<div style="display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.8rem; color: var(--text-secondary);">';
        html += '<div>Score: <strong style="color: var(--text-primary);">' + utxo.score + '/100</strong></div>';
        if (utxo.exchange_distance !== null) {
            html += '<div>Exchange: <strong style="color: var(--text-primary);">' + utxo.exchange_distance + ' hops</strong></div>';
        }
        html += '<div>Cluster: <strong style="color: var(--text-primary);">' + utxo.cluster_size + ' addrs</strong></div>';
        html += '</div>';
        html += '</div>';
    }
    html += '</div>';

    // Back button
    html += '<div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border-color);">';
    html += '<button id="cancel-selector-btn" class="button" style="width: 100%;">⬅ Enter Another Address</button>';
    html += '</div>';

    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;

    // Attach click listeners to UTXO items
    const utxoItems = document.querySelectorAll('.utxo-selector-item');
    utxoItems.forEach(item => {
        item.addEventListener('click', function() {
            const txid = this.getAttribute('data-txid');
            const vout = parseInt(this.getAttribute('data-vout'));
            runAdvancedPrivacyAnalysis(txid, vout);
        });
        item.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
        });
        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = 'none';
        });
    });

    // Attach cancel button listener
    const cancelBtn = document.getElementById('cancel-selector-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            // Clear results and return to input form
            document.getElementById('results-container').innerHTML = '';
            document.getElementById('utxo-privacy-address').value = '';
        });
    }
}

/**
 * Run advanced privacy analysis on selected UTXO
 */
async function runAdvancedPrivacyAnalysis(txid, vout) {
    currentSelectedUtxo = { txid, vout };
    showLoading();

    try {
        const result = await apiCall('/privacy/privacy-score/enhanced', {
            txid: txid,
            vout: vout,
            max_depth: 10
        });
        renderEnhancedPrivacyScore(result);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Render enhanced privacy score results
 */
function renderEnhancedPrivacyScore(r) {
    let html = '<div class="card"><div class="card-header"><div class="card-title">🔬 UTXO Privacy Analysis</div>';

    // Rating badge
    const ratingColors = { RED: 'high', YELLOW: 'medium', GREEN: 'low' };
    const ratingLabels = { RED: '🔴 Critical Privacy Risk', YELLOW: '🟡 Medium Privacy Risk', GREEN: '🟢 Good Privacy' };
    html += '<span class="cj-badge ' + (ratingColors[r.rating] || 'medium') + '">' + (ratingLabels[r.rating] || r.rating) + '</span>';
    html += '</div><div class="card-body">';

    // Overall score display
    html += '<div style="text-align: center; padding: 20px 0; margin-bottom: 20px;">';
    const scoreColor = r.overall_score >= 65 ? 'var(--accent-green)' : (r.overall_score >= 35 ? 'var(--accent-orange)' : 'var(--accent-red)');
    html += '<div style="font-size: 3rem; font-weight: 700; color: ' + scoreColor + ';">' + r.overall_score + '</div>';
    html += '<div style="color: var(--text-secondary); font-size: 1rem;">Privacy Score</div>';
    html += '</div>';

    // Summary
    html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px; margin-bottom: 20px;">';
    html += '<p style="margin: 0; font-size: 1rem; line-height: 1.5;">' + escapeHtml(r.summary) + '</p>';
    html += '</div>';

    // Critical Risks Section
    if (r.critical_risks && r.critical_risks.length > 0) {
        html += renderCriticalRisks(r.critical_risks);
    }

    // Warnings Section
    if (r.warnings && r.warnings.length > 0) {
        html += renderWarnings(r.warnings);
    }

    // Privacy Factors Breakdown (Collapsible Sections)
    if (r.privacy_factors) {
        html += '<div style="margin-bottom: 20px;">';
        html += '<h3 style="margin-bottom: 12px;">Privacy Factors Breakdown</h3>';
        html += renderPrivacyFactors(r.privacy_factors);
        html += '</div>';
    }

    // Attack Vectors
    if (r.attack_vectors && Object.keys(r.attack_vectors).length > 0) {
        html += renderAttackVectors(r.attack_vectors);
    }

    // Privacy Benchmark
    if (r.privacy_context) {
        html += renderPrivacyBenchmark(r.privacy_context);
    }

    // Recommendations
    if (r.recommendations && r.recommendations.length > 0) {
        html += renderRecommendations(r.recommendations);
    }

    // Assessment Metadata (Collapsible)
    html += renderAssessmentMetadata(r);

    // Back buttons
    html += '<div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--border-color); display: flex; gap: 12px;">';
    html += '<button id="select-another-utxo-btn" class="button" style="flex: 1;">⬅ Select Another UTXO</button>';
    html += '<button id="enter-another-address-btn" class="button" style="flex: 1;">🔄 Enter Another Address</button>';
    html += '</div>';

    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;

    // Attach event listeners
    attachBackButtonListeners();
    attachCollapsibleListeners();
    initTooltips();
}

/**
 * Render critical risks section
 */
function renderCriticalRisks(risks) {
    let html = '<div style="background: rgba(239, 68, 68, 0.1); border: 1px solid var(--accent-red); border-radius: 8px; padding: 16px; margin-bottom: 20px;">';
    html += '<div style="color: var(--accent-red); font-weight: 600; font-size: 1.1rem; margin-bottom: 12px;">⚠ Critical Privacy Risks</div>';

    for (var i = 0; i < risks.length; i++) {
        var risk = risks[i];
        html += '<div style="background: rgba(0,0,0,0.2); border-radius: 6px; padding: 12px; margin-bottom: ' + (i < risks.length - 1 ? '8px' : '0') + ';">';
        html += '<div style="display: flex; justify-content: between; align-items: flex-start; margin-bottom: 8px;">';
        html += '<div style="flex: 1;"><div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 4px;">' + escapeHtml(risk.title) + '</div>';
        if (risk.detection_confidence) {
            html += '<div style="font-size: 0.75rem; opacity: 0.8;">Confidence: ' + (risk.detection_confidence * 100).toFixed(0) + '%</div>';
        }
        html += '</div></div>';
        html += '<p style="margin: 0 0 8px 0; font-size: 0.875rem; line-height: 1.5;">' + escapeHtml(risk.description) + '</p>';
        if (risk.remediation) {
            html += '<div style="background: rgba(255,255,255,0.05); border-radius: 4px; padding: 8px; font-size: 0.8rem;">';
            html += '<strong>Remediation:</strong> ' + escapeHtml(risk.remediation);
            html += '</div>';
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

/**
 * Render warnings section
 */
function renderWarnings(warnings) {
    let html = '<div style="background: rgba(210, 153, 34, 0.1); border: 1px solid var(--accent-orange); border-radius: 8px; padding: 16px; margin-bottom: 20px;">';
    html += '<div style="color: var(--accent-orange); font-weight: 600; font-size: 1rem; margin-bottom: 12px;">⚠ Privacy Warnings</div>';

    for (var i = 0; i < warnings.length; i++) {
        var warning = warnings[i];
        html += '<div style="background: rgba(0,0,0,0.1); border-radius: 6px; padding: 12px; margin-bottom: ' + (i < warnings.length - 1 ? '8px' : '0') + ';">';
        html += '<div style="font-weight: 600; font-size: 0.9rem; margin-bottom: 4px;">' + escapeHtml(warning.title) + '</div>';
        html += '<p style="margin: 0; font-size: 0.85rem; line-height: 1.4;">' + escapeHtml(warning.description) + '</p>';
        if (warning.remediation) {
            html += '<div style="margin-top: 6px; font-size: 0.8rem; opacity: 0.9;"><strong>Fix:</strong> ' + escapeHtml(warning.remediation) + '</div>';
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

/**
 * Render privacy factors breakdown
 */
function renderPrivacyFactors(factors) {
    let html = '';
    const categoryOrder = ['temporal', 'value_analysis', 'wallet_fingerprint', 'peeling_chain', 'existing_analysis'];
    const categoryIcons = {
        temporal: '⏱',
        value_analysis: '💰',
        wallet_fingerprint: '🔍',
        peeling_chain: '🔗',
        existing_analysis: '📊'
    };
    const categoryTooltips = {
        temporal: 'Analyzes timing patterns - how quickly funds move, spend velocity, and timezone fingerprinting. Rapid spends create correlation risks.',
        value_analysis: 'Detects unique amounts (fingerprinting), subset sum leaks (where output amounts reveal input structure), and dust tracking.',
        wallet_fingerprint: 'Identifies wallet software signatures from transaction patterns - script types, output ordering (BIP-69), fee calculation, and change position.',
        peeling_chain: 'Detects peeling chains - repeated pattern of spending that creates a traceable chain of transactions. Highly damaging to privacy.',
        existing_analysis: 'Checks proximity to known exchanges (KYC risk) and CoinJoin usage (privacy enhancement). Identifies mixing protocols used.'
    };

    for (var i = 0; i < categoryOrder.length; i++) {
        var key = categoryOrder[i];
        if (!factors[key]) continue;

        var category = factors[key];
        var icon = categoryIcons[key] || '📌';
        var impactColor = category.score_impact >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';

        html += '<div class="collapsible-section" style="background: var(--bg-secondary); border-radius: 8px; margin-bottom: 8px; overflow: hidden;">';
        html += '<div class="collapsible-header" style="padding: 12px 16px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none;" data-category="' + key + '">';
        html += '<div style="display: flex; align-items: center; gap: 8px;">';
        html += '<span style="font-size: 1.1rem;">' + icon + '</span>';
        html += '<span style="font-weight: 600;">' + escapeHtml(category.category_name) + '</span>';

        // Add help icon tooltip
        var tooltipText = categoryTooltips[key] || '';
        if (tooltipText) {
            html += '<span class="help-icon" style="font-size: 0.7rem; margin-left: 4px;">?';
            html += '<span class="tooltip" style="width: 320px; z-index: 10000;">' + escapeHtml(tooltipText) + '</span>';
            html += '</span>';
        }

        html += '<span style="color: ' + impactColor + '; font-size: 0.875rem; font-weight: 600;">' + (category.score_impact >= 0 ? '+' : '') + category.score_impact + '</span>';
        html += '</div>';
        html += '<span class="collapsible-arrow" style="transition: transform 0.3s;">▼</span>';
        html += '</div>';
        html += '<div class="collapsible-content" style="max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out;">';
        html += '<div style="padding: 12px 16px; border-top: 1px solid var(--border-color);">';
        html += '<p style="margin: 0 0 12px 0; color: var(--text-secondary); font-size: 0.875rem;">' + escapeHtml(category.summary) + '</p>';

        if (category.factors && category.factors.length > 0) {
            html += '<div style="display: flex; flex-wrap: wrap; gap: 6px;">';
            for (var j = 0; j < category.factors.length; j++) {
                var factor = category.factors[j];
                var factorColor = factor.impact >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
                html += '<span style="background: var(--bg-tertiary); padding: 4px 10px; border-radius: 4px; font-size: 0.8rem; border: 1px solid var(--border-color);">';
                html += escapeHtml(factor.factor) + ' <span style="color: ' + factorColor + '; font-weight: 600;">' + (factor.impact >= 0 ? '+' : '') + factor.impact + '</span>';
                html += '</span>';
            }
            html += '</div>';
        }
        html += '</div></div></div>';
    }

    return html;
}

/**
 * Render attack vectors matrix
 */
function renderAttackVectors(vectors) {
    let html = '<div style="margin-bottom: 20px;">';
    html += '<h3 style="margin-bottom: 12px;">🎯 Attack Vector Vulnerability Matrix</h3>';
    html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px;">';
    html += '<p style="margin: 0 0 12px 0; color: var(--text-secondary); font-size: 0.875rem;">Assessment of specific attack techniques an adversary could use to compromise privacy.</p>';

    const vectorKeys = Object.keys(vectors);
    for (var i = 0; i < vectorKeys.length; i++) {
        var key = vectorKeys[i];
        var vector = vectors[key];
        var vulnScore = vector.vulnerability_score || 0;
        var barColor = vulnScore >= 0.7 ? 'var(--accent-red)' : (vulnScore >= 0.4 ? 'var(--accent-orange)' : 'var(--accent-green)');

        html += '<div style="margin-bottom: ' + (i < vectorKeys.length - 1 ? '16px' : '0') + ';">';
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">';
        html += '<span style="font-weight: 600; font-size: 0.9rem;">' + escapeHtml(vector.vector_name) + '</span>';
        html += '<span style="font-size: 0.85rem; color: ' + barColor + ';">' + (vulnScore * 100).toFixed(0) + '%</span>';
        html += '</div>';
        html += '<div style="background: var(--bg-tertiary); border-radius: 4px; height: 8px; overflow: hidden; margin-bottom: 6px;">';
        html += '<div style="background: ' + barColor + '; height: 100%; width: ' + (vulnScore * 100) + '%; transition: width 0.3s;"></div>';
        html += '</div>';
        html += '<p style="margin: 0 0 4px 0; font-size: 0.85rem; color: var(--text-secondary);">' + escapeHtml(vector.explanation) + '</p>';
        if (vector.example) {
            html += '<div style="font-size: 0.8rem; font-style: italic; opacity: 0.7;">Example: ' + escapeHtml(vector.example) + '</div>';
        }
        html += '</div>';
    }

    html += '</div></div>';
    return html;
}

/**
 * Render privacy benchmark comparison
 */
function renderPrivacyBenchmark(context) {
    let html = '<div style="margin-bottom: 20px;">';
    html += '<h3 style="margin-bottom: 12px;">📊 Privacy Benchmark</h3>';
    html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px;">';
    html += '<p style="margin: 0 0 16px 0; color: var(--text-secondary); font-size: 0.875rem;">How your privacy score compares to typical scenarios.</p>';

    if (context.benchmarks && context.benchmarks.length > 0) {
        // Sort benchmarks by score
        var sortedBenchmarks = context.benchmarks.slice().sort((a, b) => a.score - b.score);
        var currentScore = context.current_score || 0;

        html += '<div style="position: relative; padding: 20px 0;">';

        for (var i = 0; i < sortedBenchmarks.length; i++) {
            var benchmark = sortedBenchmarks[i];
            var position = (benchmark.score / 100) * 100;
            var isCurrentScore = Math.abs(benchmark.score - currentScore) < 5;

            html += '<div style="display: flex; align-items: center; margin-bottom: 12px;">';
            html += '<div style="width: 30%; font-size: 0.8rem; color: var(--text-secondary); padding-right: 12px; text-align: right;">' + escapeHtml(benchmark.scenario) + '</div>';
            html += '<div style="width: 70%; position: relative;">';
            html += '<div style="background: var(--bg-tertiary); border-radius: 4px; height: 24px; position: relative; overflow: visible;">';
            html += '<div style="background: linear-gradient(90deg, var(--accent-red), var(--accent-orange) 35%, var(--accent-green) 65%); height: 100%; width: ' + position + '%; border-radius: 4px; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;">';
            html += '<span style="font-size: 0.75rem; font-weight: 600; color: white;">' + benchmark.score + '</span>';
            html += '</div>';
            if (isCurrentScore) {
                html += '<div style="position: absolute; top: -8px; left: ' + position + '%; transform: translateX(-50%); background: var(--accent-purple); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">← You are here</div>';
            }
            html += '</div></div></div>';
        }

        html += '</div>';
    }

    if (context.percentile) {
        html += '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-color); text-align: center; font-size: 0.875rem; color: var(--text-secondary);">';
        html += 'Your score is better than <strong style="color: var(--text-primary);">' + context.percentile + '%</strong> of typical Bitcoin transactions';
        html += '</div>';
    }

    html += '</div></div>';
    return html;
}

/**
 * Render recommendations section
 */
function renderRecommendations(recommendations) {
    let html = '<div style="margin-bottom: 20px;">';
    html += '<h3 style="margin-bottom: 12px;">💡 Actionable Recommendations</h3>';
    html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px;">';

    for (var i = 0; i < recommendations.length; i++) {
        var rec = recommendations[i];
        var priorityColor = rec.priority === 'HIGH' ? 'var(--accent-red)' : (rec.priority === 'MEDIUM' ? 'var(--accent-orange)' : 'var(--accent-blue)');
        var difficultyLabel = rec.difficulty || 'UNKNOWN';

        html += '<div style="background: var(--bg-tertiary); border-left: 3px solid ' + priorityColor + '; border-radius: 6px; padding: 12px; margin-bottom: ' + (i < recommendations.length - 1 ? '12px' : '0') + ';">';
        html += '<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">';
        html += '<div style="flex: 1;">';
        html += '<div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 4px;">' + escapeHtml(rec.action) + '</div>';
        html += '<div style="display: flex; gap: 12px; font-size: 0.75rem; color: var(--text-secondary);">';
        html += '<span style="color: ' + priorityColor + '; font-weight: 600;">Priority: ' + rec.priority + '</span>';
        html += '<span>Difficulty: ' + difficultyLabel + '</span>';
        if (rec.expected_improvement) {
            html += '<span style="color: var(--accent-green); font-weight: 600;">Impact: ' + escapeHtml(rec.expected_improvement) + '</span>';
        }
        html += '</div></div></div>';
        html += '</div>';
    }

    html += '</div></div>';
    return html;
}

/**
 * Render assessment metadata (collapsible)
 */
function renderAssessmentMetadata(r) {
    let html = '<div class="collapsible-section" style="background: var(--bg-secondary); border-radius: 8px; margin-bottom: 20px; overflow: hidden;">';
    html += '<div class="collapsible-header" style="padding: 12px 16px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none;" data-category="metadata">';
    html += '<span style="font-weight: 600;">📋 Assessment Metadata</span>';
    html += '<span class="collapsible-arrow" style="transition: transform 0.3s;">▼</span>';
    html += '</div>';
    html += '<div class="collapsible-content" style="max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out;">';
    html += '<div style="padding: 12px 16px; border-top: 1px solid var(--border-color);">';

    html += '<div class="stats-grid" style="margin-bottom: 12px;">';
    html += '<div class="stat-card"><div class="stat-value">' + (r.assessment_confidence * 100).toFixed(0) + '%</div><div class="stat-label">Confidence</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (r.execution_time_ms || 0) + 'ms</div><div class="stat-label">Analysis Time</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (r.analysis_depth || 0) + '</div><div class="stat-label">Trace Depth</div></div>';
    html += '</div>';

    if (r.assessment_limitations && r.assessment_limitations.length > 0) {
        html += '<div style="margin-top: 12px;">';
        html += '<div style="font-weight: 600; margin-bottom: 6px; font-size: 0.875rem;">Analysis Limitations:</div>';
        html += '<ul style="margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 0.8rem;">';
        for (var i = 0; i < r.assessment_limitations.length; i++) {
            html += '<li style="margin-bottom: 4px;">' + escapeHtml(r.assessment_limitations[i]) + '</li>';
        }
        html += '</ul></div>';
    }

    html += '</div></div></div>';
    return html;
}

/**
 * Utility: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Attach event listeners to back buttons
 */
function attachBackButtonListeners() {
    const selectAnotherBtn = document.getElementById('select-another-utxo-btn');
    const enterAnotherBtn = document.getElementById('enter-another-address-btn');

    if (selectAnotherBtn) {
        selectAnotherBtn.addEventListener('click', showUtxoSelector);
    }

    if (enterAnotherBtn) {
        enterAnotherBtn.addEventListener('click', () => {
            // Clear results and return to input form
            document.getElementById('results-container').innerHTML = '';
            document.getElementById('utxo-privacy-address').value = '';
        });
    }
}

/**
 * Attach event listeners to collapsible sections
 */
function attachCollapsibleListeners() {
    const headers = document.querySelectorAll('.collapsible-header');
    headers.forEach(header => {
        header.addEventListener('click', function() {
            const content = this.nextElementSibling;
            const arrow = this.querySelector('.collapsible-arrow');

            if (content.style.maxHeight && content.style.maxHeight !== '0px') {
                // Collapse
                content.style.maxHeight = '0';
                arrow.style.transform = 'rotate(0deg)';
            } else {
                // Expand
                content.style.maxHeight = content.scrollHeight + 'px';
                arrow.style.transform = 'rotate(180deg)';
            }
        });
    });
}
