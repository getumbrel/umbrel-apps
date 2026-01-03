/**
 * Exchange Proximity Tool - ENHANCED VERSION
 * Analyzes how close an address is to known exchange addresses
 * with comprehensive path quality analysis and multiple path detection
 */

import { apiCall } from '../api.js';
import { showLoading, showError } from '../ui.js';

/**
 * Run exchange proximity analysis
 */
export async function analyzeExchangeProximity() {
    const address = document.getElementById('exchange-address').value.trim();
    if (!address) {
        alert('Please enter a Bitcoin address');
        return;
    }
    const maxHops = document.getElementById('exchange-hops').value;
    showLoading();
    try {
        const result = await apiCall('/privacy/exchange-proximity/' + address, { max_hops: maxHops });
        renderExchangeProximity(result);
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Get color for path quality score
 */
function getPathQualityColor(score) {
    if (score >= 85) return 'var(--accent-red)';  // STRONG - high traceability risk
    if (score >= 60) return 'var(--accent-orange)';  // MODERATE
    if (score >= 30) return 'var(--accent-yellow)';  // WEAK
    return 'var(--accent-green)';  // BROKEN - good privacy
}

/**
 * Get background color for path quality badge
 */
function getPathQualityBgColor(score) {
    if (score >= 85) return 'rgba(239, 68, 68, 0.15)';
    if (score >= 60) return 'rgba(251, 146, 60, 0.15)';
    if (score >= 30) return 'rgba(234, 179, 8, 0.15)';
    return 'rgba(34, 197, 94, 0.15)';
}

/**
 * Format path age
 */
function formatPathAge(days) {
    if (days === null || days === undefined) return 'Unknown';
    if (days < 1) return 'Less than 1 day';
    if (days < 30) return Math.round(days) + ' days ago';
    if (days < 365) return Math.round(days / 30) + ' months ago';
    return (days / 365).toFixed(1) + ' years ago';
}

/**
 * Render enhanced exchange proximity results
 * @param {Object} r - API response data
 */
function renderExchangeProximity(r) {
    let html = '<div class="card"><div class="card-header"><div class="card-title">🏦 Exchange Proximity Analysis (Enhanced)</div>';

    // Risk badge
    const riskColors = { low: 'low', medium: 'medium', high: 'high', critical: 'high' };
    const riskLabels = { low: '✓ Distant', medium: '⚠ Moderate', high: '⚠ Close', critical: '🚨 Direct Link' };
    html += '<span class="cj-badge ' + (riskColors[r.risk_level] || 'medium') + '">' + (riskLabels[r.risk_level] || r.risk_level) + '</span>';
    html += '</div><div class="card-body">';

    // =========================================================================
    // SECTION A: Overall Summary (Enhanced)
    // =========================================================================
    html += '<div style="text-align: center; padding: 20px 0; margin-bottom: 20px; border-bottom: 2px solid var(--border-color);">';

    if (r.hops_to_exchange !== null) {
        const hopColor = r.hops_to_exchange <= 2 ? 'var(--accent-red)' : (r.hops_to_exchange <= 4 ? 'var(--accent-orange)' : 'var(--accent-green)');
        html += '<div style="font-size: 3rem; font-weight: 700; color: ' + hopColor + ';">' + r.hops_to_exchange + '</div>';
        html += '<div style="color: var(--text-secondary); font-size: 1rem;">hops from <strong style="color: var(--text-primary);">' + r.nearest_exchange + '</strong></div>';

        if (r.direction) {
            const dirLabel = r.direction === 'received_from' ? 'Received funds from' : (r.direction === 'sent_to' ? 'Sent funds to' : 'Is');
            html += '<div style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 4px;">' + dirLabel + ' exchange</div>';
        }

        // Path strength badge
        if (r.path_strength) {
            const strengthColor = getPathQualityColor(r.path_quality_score || 0);
            const strengthBg = getPathQualityBgColor(r.path_quality_score || 0);
            html += '<div style="margin-top: 12px;">';
            html += '<span style="display: inline-block; padding: 6px 16px; border-radius: 20px; background: ' + strengthBg + '; color: ' + strengthColor + '; font-weight: 600; font-size: 0.875rem;">';
            html += r.path_strength + ' LINK';
            html += '</span></div>';
        }
    } else {
        html += '<div style="font-size: 2rem; font-weight: 700; color: var(--accent-green);">No Exchange Found</div>';
        html += '<div style="color: var(--text-secondary); font-size: 0.875rem;">Within ' + (document.getElementById('exchange-hops').value || 6) + ' hops</div>';
    }
    html += '</div>';

    // =========================================================================
    // SECTION B: Path Quality Analysis (NEW)
    // =========================================================================
    if (r.path_quality_score !== undefined && r.hops_to_exchange !== null) {
        html += '<div style="margin-bottom: 24px;">';
        html += '<h3 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">';
        html += '<span>🔍 Path Quality Analysis</span>';
        html += '<span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Measures how traceable the link is. Lower scores indicate privacy-enhancing techniques (CoinJoins) were used.</span></span>';
        html += '</h3>';

        html += '<div style="background: var(--bg-secondary); border-radius: 12px; padding: 20px;">';

        // Quality score with progress bar
        const qualityColor = getPathQualityColor(r.path_quality_score);
        const qualityBg = getPathQualityBgColor(r.path_quality_score);

        html += '<div style="margin-bottom: 16px;">';
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">';
        html += '<span style="font-weight: 600;">Path Quality Score</span>';
        html += '<span style="font-size: 1.5rem; font-weight: 700; color: ' + qualityColor + ';">' + r.path_quality_score + '/100</span>';
        html += '</div>';

        // Progress bar
        html += '<div style="width: 100%; height: 12px; background: var(--bg-primary); border-radius: 6px; overflow: hidden;">';
        html += '<div style="width: ' + r.path_quality_score + '%; height: 100%; background: linear-gradient(90deg, ' + qualityColor + ', ' + qualityColor + '99); transition: width 0.5s ease;"></div>';
        html += '</div>';

        // Interpretation
        html += '<div style="margin-top: 8px; padding: 12px; background: ' + qualityBg + '; border-radius: 8px; border-left: 3px solid ' + qualityColor + ';">';
        if (r.path_quality_score >= 85) {
            html += '<div style="color: ' + qualityColor + '; font-weight: 600;">🚨 STRONG LINK - High Traceability Risk</div>';
            html += '<div style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 4px;">This transaction path is easily traceable. Chain analysis can link this to your KYC identity with high confidence.</div>';
        } else if (r.path_quality_score >= 60) {
            html += '<div style="color: ' + qualityColor + '; font-weight: 600;">⚠ MODERATE LINK - Some Privacy Protection</div>';
            html += '<div style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 4px;">Some privacy techniques detected, but sophisticated analysis may still trace this connection.</div>';
        } else if (r.path_quality_score >= 30) {
            html += '<div style="color: ' + qualityColor + '; font-weight: 600;">✓ WEAK LINK - Good Privacy Practices</div>';
            html += '<div style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 4px;">Privacy-enhancing techniques have significantly reduced traceability.</div>';
        } else {
            html += '<div style="color: ' + qualityColor + '; font-weight: 600;">✅ BROKEN LINK - Excellent Privacy</div>';
            html += '<div style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 4px;">CoinJoins or mixers have effectively broken the heuristic link to the exchange. Well done!</div>';
        }
        html += '</div>';
        html += '</div>';

        // Quality factors
        if (r.path_quality_factors && r.path_quality_factors.length > 0) {
            html += '<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-color);">';
            html += '<div style="font-weight: 600; margin-bottom: 8px; font-size: 0.875rem;">Factors Affecting Quality:</div>';
            html += '<ul style="margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 0.875rem; line-height: 1.8;">';
            for (var i = 0; i < r.path_quality_factors.length; i++) {
                const factor = r.path_quality_factors[i];
                const isNegative = factor.includes('-');
                const icon = isNegative ? '🔴' : '🟢';
                html += '<li style="margin-bottom: 4px;">' + icon + ' ' + factor + '</li>';
            }
            html += '</ul></div>';
        }

        // Key metrics
        html += '<div style="margin-top: 16px; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px;">';

        // CoinJoin count
        const cjColor = (r.coinjoin_count_in_path || 0) > 0 ? 'var(--accent-green)' : 'var(--text-secondary)';
        html += '<div style="text-align: center; padding: 12px; background: var(--bg-primary); border-radius: 8px;">';
        html += '<div style="font-size: 1.5rem; font-weight: 700; color: ' + cjColor + ';">' + (r.coinjoin_count_in_path || 0) + '</div>';
        html += '<div style="font-size: 0.75rem; color: var(--text-secondary);">CoinJoins Detected</div>';
        html += '</div>';

        // Path age
        html += '<div style="text-align: center; padding: 12px; background: var(--bg-primary); border-radius: 8px;">';
        html += '<div style="font-size: 1rem; font-weight: 600; color: var(--text-primary);">' + formatPathAge(r.path_age_days) + '</div>';
        html += '<div style="font-size: 0.75rem; color: var(--text-secondary);">Path Age</div>';
        html += '</div>';

        html += '</div>';
        html += '</div></div>';
    }

    // =========================================================================
    // SECTION C: Stats Grid
    // =========================================================================
    html += '<div class="stats-grid" style="margin-bottom: 24px;">';
    html += '<div class="stat-card"><div class="stat-value" style="color: ' + (r.proximity_score > 50 ? 'var(--accent-red)' : 'var(--accent-green)') + ';">' + r.proximity_score + '</div><div class="stat-label">Proximity Score <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">0-100 score where 100 means directly connected to exchange. Higher = easier to trace.</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (r.nearest_exchange || 'None') + '</div><div class="stat-label">Nearest Exchange</div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + (r.all_exchange_connections ? r.all_exchange_connections.length : (r.exchange_connections ? r.exchange_connections.length : 0)) + '</div><div class="stat-label">Exchanges Found <span class="help-icon" style="font-size: 0.7rem;">?<span class="tooltip">Total number of unique exchange connections discovered.</span></span></div></div>';
    html += '<div class="stat-card"><div class="stat-value">' + r.execution_time_ms + 'ms</div><div class="stat-label">Analysis Time</div></div>';
    html += '</div>';

    // =========================================================================
    // SECTION D: All Exchange Connections (NEW)
    // =========================================================================
    if (r.all_exchange_connections && r.all_exchange_connections.length > 0) {
        html += '<div style="margin-bottom: 24px;">';
        html += '<h3 style="margin-bottom: 12px;">🌐 All Exchange Connections Found (' + r.all_exchange_connections.length + ')</h3>';
        html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px; max-height: 400px; overflow-y: auto;">';

        for (var j = 0; j < r.all_exchange_connections.length; j++) {
            var conn = r.all_exchange_connections[j];
            var connColor = conn.hops <= 2 ? 'var(--accent-red)' : (conn.hops <= 4 ? 'var(--accent-orange)' : 'var(--accent-green)');
            var qualColor = getPathQualityColor(conn.path_quality || 0);

            html += '<div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--bg-primary); border-radius: 8px; margin-bottom: 8px; border-left: 3px solid ' + connColor + ';">';
            html += '<div style="flex: 1;">';
            html += '<div style="font-weight: 600; color: var(--text-primary);">' + (j + 1) + '. ' + conn.exchange + '</div>';
            html += '<div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">';
            html += conn.type + ' • ' + conn.direction.replace('_', ' ');
            html += '</div></div>';
            html += '<div style="text-align: right;">';
            html += '<div style="font-weight: 600; color: ' + connColor + ';">' + conn.hops + ' hops</div>';
            html += '<div style="font-size: 0.75rem; color: ' + qualColor + '; margin-top: 2px;">' + conn.path_strength + '</div>';
            html += '</div></div>';
        }

        html += '</div></div>';
    }

    // =========================================================================
    // SECTION E: Alternative Paths (NEW)
    // =========================================================================
    if (r.alternative_paths && r.alternative_paths.length > 1) {
        html += '<div style="margin-bottom: 24px;">';
        html += '<h3 style="margin-bottom: 12px;">🔀 Alternative Paths Found (' + r.alternative_paths.length + ')</h3>';
        html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px;">';
        html += '<div style="color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 12px;">Multiple paths to exchanges were discovered. Paths are ranked by hop count and quality.</div>';

        for (var k = 0; k < r.alternative_paths.length; k++) {
            var altPath = r.alternative_paths[k];
            var pathColor = getPathQualityColor(altPath.path_quality_score || 0);
            var isCurrentPath = k === 0;

            html += '<div style="padding: 12px; background: var(--bg-primary); border-radius: 8px; margin-bottom: 8px; border: ' + (isCurrentPath ? '2px solid var(--accent-purple)' : '1px solid var(--border-color)') + ';">';
            html += '<div style="display: flex; justify-content: between; align-items: center; margin-bottom: 8px;">';
            html += '<div><span style="font-weight: 600;">Path ' + (k + 1) + '</span>';
            if (isCurrentPath) {
                html += ' <span style="font-size: 0.75rem; padding: 2px 8px; background: var(--accent-purple); color: white; border-radius: 12px; margin-left: 8px;">Nearest</span>';
            }
            html += '</div>';
            html += '<div style="text-align: right;">';
            html += '<span style="color: ' + pathColor + '; font-weight: 600;">' + altPath.path_strength + '</span>';
            html += ' <span style="color: var(--text-secondary); font-size: 0.875rem;">(' + altPath.path_quality_score + '/100)</span>';
            html += '</div></div>';

            html += '<div style="font-size: 0.875rem; color: var(--text-secondary);">';
            html += '→ ' + altPath.exchange_name + ' via ' + altPath.total_hops + ' hops';
            if (altPath.coinjoin_count > 0) {
                html += ' • <span style="color: var(--accent-green);">' + altPath.coinjoin_count + ' CoinJoin(s)</span>';
            }
            if (altPath.path_age_days) {
                html += ' • ' + formatPathAge(altPath.path_age_days);
            }
            html += '</div>';
            html += '</div>';
        }

        html += '</div></div>';
    }

    // =========================================================================
    // SECTION F: Detailed Transaction Path (Enhanced)
    // =========================================================================
    if (r.path_to_exchange && r.path_to_exchange.length > 0) {
        html += '<h3 style="margin-bottom: 12px;">🔗 Detailed Transaction Path</h3>';
        html += '<div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px;">';

        for (var m = 0; m < r.path_to_exchange.length; m++) {
            var hop = r.path_to_exchange[m];
            html += '<div style="display: flex; align-items: center; gap: 12px; padding: 12px 0;' + (m > 0 ? ' border-top: 1px solid var(--border-color);' : '') + '">';

            // Hop number
            html += '<div style="background: var(--accent-purple); color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.875rem; font-weight: 600; flex-shrink: 0;">' + hop.hop_number + '</div>';

            // Hop details
            html += '<div style="flex: 1; min-width: 0;">';
            html += '<div class="mono" style="font-size: 0.8rem; overflow: hidden; text-overflow: ellipsis;">' + hop.address.substring(0, 20) + '...' + hop.address.slice(-12) + '</div>';
            html += '<div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px;">';
            html += hop.value_btc.toFixed(8) + ' BTC • ' + hop.direction.replace('_', ' ');

            // CoinJoin badge
            if (hop.is_coinjoin) {
                html += ' • <span style="color: var(--accent-green); font-weight: 600;">🔀 CoinJoin</span>';
            }

            // Block height/age
            if (hop.block_height) {
                html += ' • Block ' + hop.block_height;
            }

            html += '</div></div>';

            // Direction arrow
            if (m < r.path_to_exchange.length - 1) {
                html += '<div style="color: var(--text-secondary); font-size: 1.5rem;">→</div>';
            }

            html += '</div>';
        }

        html += '</div>';
    }

    // =========================================================================
    // SECTION G: Enhanced Recommendations
    // =========================================================================
    if (r.recommendations && r.recommendations.length > 0) {
        // Determine recommendation style based on risk level
        var recoBg = 'var(--bg-secondary)';
        var recoIcon = '💡';
        var recoTitle = 'Recommendations';

        if (r.risk_level === 'critical' || (r.path_quality_score && r.path_quality_score >= 85)) {
            recoBg = 'rgba(239, 68, 68, 0.1)';
            recoIcon = '🚨';
            recoTitle = 'Urgent Recommendations';
        } else if (r.path_quality_score && r.path_quality_score < 30) {
            recoBg = 'rgba(34, 197, 94, 0.1)';
            recoIcon = '✅';
            recoTitle = 'Good Privacy Detected';
        }

        html += '<div style="margin-top: 24px; background: ' + recoBg + '; border-radius: 8px; padding: 16px;">';
        html += '<div style="font-weight: 600; margin-bottom: 12px;">' + recoIcon + ' ' + recoTitle + '</div>';
        html += '<ul style="margin: 0; padding-left: 20px; color: var(--text-secondary); font-size: 0.875rem; line-height: 1.8;">';
        for (var n = 0; n < r.recommendations.length; n++) {
            html += '<li style="margin-bottom: 6px;">' + r.recommendations[n] + '</li>';
        }
        html += '</ul></div>';
    }

    // =========================================================================
    // SECTION H: Warnings
    // =========================================================================
    if (r.warnings && r.warnings.length > 0) {
        html += '<div style="margin-top: 16px; background: rgba(251, 146, 60, 0.1); border: 1px solid var(--accent-orange); border-radius: 8px; padding: 12px;">';
        html += '<div style="font-weight: 600; color: var(--accent-orange); margin-bottom: 8px;">⚠️ Analysis Warnings</div>';
        html += '<ul style="margin: 0; padding-left: 20px; color: var(--accent-orange); font-size: 0.875rem;">';
        for (var p = 0; p < r.warnings.length; p++) {
            html += '<li style="margin-bottom: 4px;">' + r.warnings[p] + '</li>';
        }
        html += '</ul></div>';
    }

    // =========================================================================
    // Educational Footer
    // =========================================================================
    html += '<div style="margin-top: 24px; padding-top: 16px; border-top: 2px solid var(--border-color); font-size: 0.75rem; color: var(--text-secondary);">';
    html += '<strong>How to interpret these results:</strong><br>';
    html += '• <strong>Path Quality Score:</strong> Lower scores (0-30) indicate good privacy from CoinJoins/mixers breaking the link<br>';
    html += '• <strong>Path Strength:</strong> BROKEN/WEAK = good privacy, STRONG = easily traceable<br>';
    html += '• <strong>Hops:</strong> More hops = more distance from exchange, but without CoinJoins hop count alone doesn\'t guarantee privacy<br>';
    html += '• <strong>CoinJoins:</strong> Privacy-enhancing transactions that mix your coins with others to break traceability<br>';
    html += '</div>';

    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;
}
