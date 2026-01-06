/**
 * KYC Privacy Check Tool
 * Analyzes privacy impact of KYC-linked exchange withdrawals
 */

import { apiCall } from '../api.js';
import { showLoading, showError } from '../ui.js';
import { createTruncatedValue, formatBTC } from '../utils.js';

/**
 * Run KYC Privacy Check analysis
 */
export async function runKYCPrivacyCheck() {
    const txid = document.getElementById('kyc-txid').value.trim();
    const address = document.getElementById('kyc-address').value.trim();
    const depth = document.getElementById('kyc-depth').value;

    if (!txid) {
        alert('Please enter the exchange withdrawal transaction ID');
        return;
    }
    if (!address) {
        alert('Please enter the address you withdrew to');
        return;
    }

    showLoading('Analyzing your privacy... This may take a moment.');
    try {
        const result = await apiCall('/kyc/trace', {
            exchange_txid: txid,
            destination_address: address,
            depth_preset: depth
        });
        renderKYCResult(result);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Toggle Risk Intelligence section visibility
 */
export function toggleRiskIntelligence() {
    const content = document.getElementById('risk-intelligence-content');
    const icon = document.getElementById('risk-toggle-icon');

    if (content && icon) {
        if (content.style.display === 'none') {
            content.style.display = 'block';
            icon.textContent = '▲';
        } else {
            content.style.display = 'none';
            icon.textContent = '▼';
        }
    }
}

/**
 * Render Risk Intelligence section
 * @param {Object} risks - Risk intelligence data
 * @returns {string} HTML string
 */
function renderRiskIntelligence(risks) {
    let html = '';

    // CRITICAL Risks
    if (risks.critical && risks.critical.length > 0) {
        html += `
            <div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 1.2rem;">🔴</span>
                    <span style="font-weight: 600; color: var(--accent-red);">CRITICAL RISKS</span>
                </div>
                <ul style="list-style: none; padding: 0; margin: 0;">
        `;

        risks.critical.forEach(risk => {
            html += `
                <li style="padding: 8px 0 8px 32px; color: var(--text-primary); font-size: 0.875rem;">
                    • ${risk.description}
                    ${risk.address ? `<br><span style="color: var(--text-secondary); font-size: 0.8rem; margin-left: 10px;">Detected at: ${risk.address.substring(0, 20)}...</span>` : ''}
                </li>
            `;
        });

        html += `
                </ul>
            </div>
        `;
    }

    // MEDIUM Risks
    if (risks.medium && risks.medium.length > 0) {
        html += `
            <div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 1.2rem;">🟡</span>
                    <span style="font-weight: 600; color: var(--accent-orange);">MEDIUM RISKS</span>
                </div>
                <ul style="list-style: none; padding: 0; margin: 0;">
        `;

        risks.medium.forEach(risk => {
            html += `
                <li style="padding: 8px 0 8px 32px; color: var(--text-primary); font-size: 0.875rem;">
                    • ${risk.description}
                </li>
            `;
        });

        html += `
                </ul>
            </div>
        `;
    }

    // POSITIVE Factors
    if (risks.positive && risks.positive.length > 0) {
        html += `
            <div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 1.2rem;">🟢</span>
                    <span style="font-weight: 600; color: var(--accent-green);">POSITIVE FACTORS</span>
                </div>
                <ul style="list-style: none; padding: 0; margin: 0;">
        `;

        risks.positive.forEach(positive => {
            html += `
                <li style="padding: 8px 0 8px 32px; color: var(--text-primary); font-size: 0.875rem;">
                    • ${positive.description}
                </li>
            `;
        });

        html += `
                </ul>
            </div>
        `;
    }

    return html || '<p style="color: var(--text-secondary);">No specific risks identified.</p>';
}

/**
 * Render Privacy Impact warning for a destination
 * @param {Object} dest - Destination object
 * @returns {string} HTML string
 */
function renderPrivacyImpact(dest) {
    if (!dest.entity_name) return '';

    const impactColor = dest.entity_risk_level === 'critical' ? 'var(--accent-red)' :
                       dest.entity_risk_level === 'high' ? 'var(--accent-orange)' :
                       'var(--accent-blue)';

    let impactText = '';
    if (dest.entity_type === 'exchange') {
        impactText = `${dest.entity_name} knows you own these funds and can track all future spends`;
    } else if (dest.entity_type === 'mixer') {
        impactText = `Mixing service provides some privacy but maintains logs`;
    } else {
        impactText = `Entity type: ${dest.entity_type}`;
    }

    return `
        <div style="margin-top: 12px; padding: 10px; background: rgba(248, 81, 73, 0.1); border-left: 3px solid ${impactColor}; border-radius: 4px;">
            <div style="font-weight: 600; color: ${impactColor}; margin-bottom: 4px;">⚠️ PRIVACY IMPACT</div>
            <div style="font-size: 0.85rem; color: var(--text-secondary);">${impactText}</div>
        </div>
    `;
}

/**
 * Render reasoning list for a destination
 * @param {Array} reasoning - Array of reasoning strings
 * @returns {string} HTML string
 */
function renderReasoning(reasoning) {
    if (!reasoning || reasoning.length === 0) return '';

    let html = '<div class="destination-reasoning"><strong>Why:</strong><ul>';
    reasoning.forEach(reason => {
        html += `<li>${reason}</li>`;
    });
    html += '</ul></div>';

    return html;
}

/**
 * Render KYC Privacy Check results
 * @param {Object} result - API response data
 */
function renderKYCResult(result) {
    const pc = result.privacy_rating;
    const dests = result.probable_destinations || [];
    const badgeClass = (pc === 'excellent' || pc === 'good') ? 'low' : (pc === 'moderate' ? 'medium' : 'high');

    let html = '<div class="card"><div class="card-header"><div class="card-title">🕵️ KYC Privacy Analysis</div>';
    html += '<span class="cj-badge ' + badgeClass + '">' + pc.toUpperCase() + ' PRIVACY</span></div><div class="card-body">';
    html += '<div class="privacy-score" style="margin-bottom: 24px;"><div class="score-circle ' + pc + '">' + result.overall_privacy_score.toFixed(0) + '</div>';
    html += '<div class="score-details"><div class="score-rating">' + pc.replace('_', ' ') + ' Privacy</div>';
    html += '<div class="score-summary">' + result.summary + '</div></div></div>';

    html += '<div class="stats-grid" style="margin-bottom: 24px;">';
    html += '<div class="stat-card"><div class="stat-value">' + (result.original_value_btc ? result.original_value_btc.toFixed(8) : '0') + '</div><div class="stat-label">Original BTC</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + result.destination_count + '</div><div class="stat-label">Destinations</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + result.high_confidence_destinations + '</div><div class="stat-label">High Confidence</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + result.coinjoins_encountered + '</div><div class="stat-label">Unique CoinJoins <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total unique CoinJoin transactions detected across all traced paths from your withdrawal address.</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (result.untraceable_percent ? result.untraceable_percent.toFixed(1) : 0) + '%</div><div class="stat-label">Untraceable</div></div>';
    html += '</div>';

    // NEW: Risk Intelligence Section (Collapsible)
    if (result.risk_intelligence && result.enhanced) {
        const totalRisks = (result.risk_intelligence.critical?.length || 0) +
                          (result.risk_intelligence.medium?.length || 0);
        const totalPositive = result.risk_intelligence.positive?.length || 0;

        html += `
            <div style="margin-top: 20px;">
                <div class="risk-intelligence-header" onclick="toggleRiskIntelligence()" style="cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 12px; background: var(--bg-tertiary); border-radius: 6px; border: 1px solid var(--border-color);">
                    <span style="font-size: 1.1rem;">🎯</span>
                    <span style="font-weight: 600; flex: 1;">Risk Intelligence</span>
                    <span style="font-size: 0.85rem; color: var(--text-secondary);">
                        ${totalRisks} risk${totalRisks !== 1 ? 's' : ''}, ${totalPositive} positive
                    </span>
                    <span id="risk-toggle-icon" style="font-size: 0.9rem; color: var(--text-secondary);">▼</span>
                </div>
                <div id="risk-intelligence-content" style="display: none; margin-top: 12px; padding: 16px; background: var(--bg-tertiary); border-radius: 6px; border: 1px solid var(--border-color);">
                    ${renderRiskIntelligence(result.risk_intelligence)}
                </div>
            </div>
        `;
    }

    if (!result.electrs_enabled) {
        html += '<div style="background: rgba(210, 153, 34, 0.1); border: 1px solid var(--accent-orange); border-radius: 8px; padding: 12px; margin-bottom: 16px; margin-top: 16px;"><span style="color: var(--accent-orange);">⚠️ Fulcrum Not Available</span> - Analysis may be incomplete.</div>';
    }
    if (result.warnings && result.warnings.length > 0) {
        html += '<div style="background: rgba(248, 81, 73, 0.1); border: 1px solid var(--accent-red); border-radius: 8px; padding: 12px; margin-bottom: 16px; margin-top: 16px;"><strong style="color: var(--accent-red);">⚠️ Warnings:</strong><ul style="margin: 8px 0 0 20px; color: var(--text-secondary);">';
        for (var i = 0; i < result.warnings.length; i++) {
            html += '<li>' + result.warnings[i] + '</li>';
        }
        html += '</ul></div>';
    }
    html += '</div></div>';

    if (dests.length > 0) {
        html += '<div class="card"><div class="card-header"><div class="card-title">📍 Probable Current Holdings</div><span class="cj-badge info">' + dests.length + ' destination(s)</span></div><div class="card-body">';
        html += '<p style="color: var(--text-secondary); margin-bottom: 16px;">These are addresses where your funds likely ended up. Higher confidence = easier to trace.</p>';

        // Process each destination with enhanced display
        dests.forEach((dest, index) => {
            // Determine confidence class - support both old and new field names
            const confidenceScore = dest.confidence_score || (parseFloat(dest.confidence_percent) / 100) || 0;
            const confidenceLevel = dest.confidence_level ||
                                   (confidenceScore >= 0.7 ? 'high' : confidenceScore >= 0.4 ? 'medium' : 'low');
            const confidencePercent = dest.confidence_percent || Math.round(confidenceScore * 100) + '%';

            // Trail status for legacy display
            const trailText = dest.trail_status === 'cold' ? '🥶 Trail Cold' :
                            (dest.trail_status === 'dead_end' ? '💰 Unspent' :
                            (dest.trail_status === 'depth_limit' ? '⏱️ Depth Limit' : '❓ Lost'));

            const confColor = confidenceLevel === 'high' ? 'var(--accent-red)' :
                            (confidenceLevel === 'medium' ? 'var(--accent-orange)' : 'var(--accent-green)');

            // NEW: Entity badge
            let entityBadge = '';
            if (dest.entity_name) {
                const riskColor = dest.entity_risk_level === 'critical' ? 'var(--accent-red)' :
                                 dest.entity_risk_level === 'high' ? 'var(--accent-orange)' :
                                 'var(--accent-blue)';

                entityBadge = `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding: 8px; background: rgba(248, 81, 73, 0.1); border-radius: 4px; border-left: 3px solid ${riskColor};">
                        <span style="font-size: 1.2rem;">${dest.entity_emoji || '🏢'}</span>
                        <div>
                            <div style="font-weight: 600; color: ${riskColor};">${(dest.entity_type || 'entity').toUpperCase()} IDENTIFIED</div>
                            <div style="font-size: 0.85rem; color: var(--text-secondary);">Entity: ${dest.entity_name} (confidence: ${Math.round((dest.entity_confidence || 0) * 100)}%)</div>
                        </div>
                    </div>
                `;
            }

            // NEW: Timestamp display
            let timestampDisplay = '';
            if (dest.age_human) {
                timestampDisplay = `<span style="color: var(--text-secondary);">⏱ ${dest.age_human}</span>`;
            }

            // Get path info - support both old and new field names
            const pathLength = dest.path_info?.hops || dest.path_length || 0;
            const coinjoinsCount = dest.path_info?.coinjoin_count || dest.coinjoins_passed || 0;
            const valueBtc = dest.value_btc || 0;

            html += `<div class="destination-card ${confidenceLevel}-confidence" style="margin-bottom: 16px;">`;

            // Entity badge at top if present
            if (entityBadge) {
                html += entityBadge;
            }

            // Header section
            html += '<div class="destination-header"><div><div class="destination-address">' +
                    createTruncatedValue(dest.address, dest.address.substring(0, 12) + '...' + dest.address.slice(-6), 'kyc-dest-' + index) +
                    '</div>';

            // Show trail status if available (legacy field)
            if (dest.trail_status) {
                html += `<span class="trail-status ${dest.trail_status}">${trailText}</span>`;
            }

            html += '</div>';
            html += `<div class="destination-confidence ${confidenceLevel}">${confidencePercent}</div></div>`;

            // Stats section with timestamp
            html += '<div class="destination-details">';
            html += `<div class="destination-stat"><div class="destination-stat-value">${formatBTC(valueBtc)}</div><div class="destination-stat-label">BTC</div></div>`;
            html += `<div class="destination-stat"><div class="destination-stat-value">${pathLength}</div><div class="destination-stat-label">Hops</div></div>`;
            html += `<div class="destination-stat"><div class="destination-stat-value">${coinjoinsCount}</div><div class="destination-stat-label">CoinJoins <span class="help-icon" style="font-size: 0.6rem;">?<span class="tooltip">Number of CoinJoin transactions in this specific path.</span></span></div></div>`;
            html += `<div class="destination-stat"><div class="destination-stat-value" style="color: ${confColor}; font-size: 0.9rem;">${confidenceLevel.toUpperCase()}</div><div class="destination-stat-label">${timestampDisplay}</div></div>`;
            html += '</div>';

            // Reasoning section
            if (dest.reasoning && dest.reasoning.length > 0) {
                html += renderReasoning(dest.reasoning);
            }

            // NEW: Privacy Impact section
            if (dest.entity_name) {
                html += renderPrivacyImpact(dest);
            }

            html += '</div>';
        });

        html += '</div></div>';
    }

    // Recommendations - support both prioritized (new) and legacy (old) formats
    if (result.recommendations_prioritized && result.recommendations_prioritized.length > 0) {
        // NEW: Priority-ranked recommendations
        html += '<div class="card"><div class="card-header"><div class="card-title">💡 Recommendations (Priority-Ranked)</div></div><div class="card-body">';

        // Group by priority
        const urgent = result.recommendations_prioritized.filter(r => r.priority === 'URGENT');
        const important = result.recommendations_prioritized.filter(r => r.priority === 'IMPORTANT');
        const bestPractice = result.recommendations_prioritized.filter(r => r.priority === 'BEST_PRACTICE');

        // URGENT section
        if (urgent.length > 0) {
            html += `<div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 1.2rem;">🚨</span>
                    <span style="font-weight: 600; color: var(--accent-red);">URGENT (Address within 24 hours)</span>
                </div>`;
            urgent.forEach(rec => {
                html += `<div style="margin-left: 32px; margin-bottom: 8px; padding: 12px; background: rgba(248, 81, 73, 0.1); border-left: 3px solid var(--accent-red); border-radius: 4px;">
                    <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">• ${rec.action}</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">${rec.recommendation}</div>
                    ${rec.expected_improvement ? `<div style="font-size: 0.8rem; color: var(--accent-green); margin-top: 4px;">Expected improvement: ${rec.expected_improvement}</div>` : ''}
                </div>`;
            });
            html += `</div>`;
        }

        // IMPORTANT section
        if (important.length > 0) {
            html += `<div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 1.2rem;">⚠️</span>
                    <span style="font-weight: 600; color: var(--accent-orange);">IMPORTANT (Address this week)</span>
                </div>`;
            important.forEach(rec => {
                html += `<div style="margin-left: 32px; margin-bottom: 8px; padding: 12px; background: rgba(210, 153, 34, 0.1); border-left: 3px solid var(--accent-orange); border-radius: 4px;">
                    <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">• ${rec.action}</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">${rec.recommendation}</div>
                    ${rec.expected_improvement ? `<div style="font-size: 0.8rem; color: var(--accent-green); margin-top: 4px;">Expected improvement: ${rec.expected_improvement}</div>` : ''}
                </div>`;
            });
            html += `</div>`;
        }

        // BEST_PRACTICE section
        if (bestPractice.length > 0) {
            html += `<div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 1.2rem;">💡</span>
                    <span style="font-weight: 600; color: var(--accent-blue);">BEST PRACTICES (General advice)</span>
                </div>`;
            bestPractice.forEach(rec => {
                html += `<div style="margin-left: 32px; margin-bottom: 8px; padding: 12px; background: var(--bg-tertiary); border-left: 3px solid var(--accent-blue); border-radius: 4px;">
                    <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">• ${rec.action}</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">${rec.recommendation}</div>
                    ${rec.expected_improvement ? `<div style="font-size: 0.8rem; color: var(--accent-green); margin-top: 4px;">Expected improvement: ${rec.expected_improvement}</div>` : ''}
                </div>`;
            });
            html += `</div>`;
        }

        html += '</div></div>';
    } else if (result.recommendations && result.recommendations.length > 0) {
        // LEGACY: Simple recommendation list
        html += '<div class="card"><div class="card-header"><div class="card-title">💡 Recommendations</div></div><div class="card-body"><ul class="factor-list">';
        for (var m = 0; m < result.recommendations.length; m++) {
            html += '<li class="factor-item"><span class="factor-impact positive">TIP</span>' + result.recommendations[m] + '</li>';
        }
        html += '</ul></div></div>';
    }

    html += '<div class="card"><div class="card-header"><div class="card-title">ℹ️ Analysis Details</div></div><div class="card-body"><div class="tx-details">';
    html += '<div class="tx-row"><span class="tx-label">Exchange TX</span><span class="tx-value">' + createTruncatedValue(result.exchange_txid, result.exchange_txid.substring(0, 16) + '...', 'kyc-txid') + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Withdrawal Address</span><span class="tx-value">' + createTruncatedValue(result.destination_address, result.destination_address.substring(0, 12) + '...' + result.destination_address.slice(-6), 'kyc-addr') + '</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Scan Depth</span><span class="tx-value">' + result.trace_depth + ' hops</span></div>';
    html += '<div class="tx-row"><span class="tx-label">Time</span><span class="tx-value">' + result.execution_time_ms + 'ms</span></div>';
    html += '</div></div></div>';

    document.getElementById('results-container').innerHTML = html;
}
