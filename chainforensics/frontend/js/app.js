/**
 * ChainForensics - Main Application Entry Point
 * Imports all modules and initializes the application
 */

// Import configuration and utilities
import { API_BASE, DONATION_ADDRESS } from './config.js';
import { apiCall } from './api.js';
import {
    formatBTC,
    createTruncatedValue,
    copyToClipboard,
    copyAddress,
    toggleSection
} from './utils.js';
import {
    showLoading,
    hideLoading,
    showError,
    openDonationModal,
    closeDonationModal,
    initTooltips,
    initModals,
    initDonationAddress
} from './ui.js';

// Import tool modules
import { runKYCPrivacyCheck, toggleRiskIntelligence } from './tools/kyc.js';
import { detectCluster } from './tools/cluster.js';
import { analyzeExchangeProximity } from './tools/exchange.js';
import { analyzeUTXOPrivacy } from './tools/utxo-privacy.js';
import {
    analyzeTransaction,
    traceUTXO,
    detectCoinJoin,
    calculatePrivacy
} from './tools/transaction.js';
import {
    validateAddress,
    getAddressInfo,
    checkDustAttack
} from './tools/address.js';
import { loadLabels } from './tools/labels.js';

// Import visualization module
import {
    openVisualization,
    closeVisualization,
    visZoomIn,
    visZoomOut,
    visFitAll,
    initVisualizationModal
} from './visualization.js';

/**
 * Check API and node health status
 */
async function checkHealth() {
    try {
        const health = await apiCall('/health');
        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');

        if (health.status === 'healthy') {
            dot.classList.remove('disconnected');
            text.textContent = 'Bitcoin Node: Connected';
        } else {
            dot.classList.add('disconnected');
            text.textContent = 'Bitcoin Node: Degraded';
        }

        // Update Bitcoin Core stats
        if (health.components && health.components.bitcoin_core) {
            const btc = health.components.bitcoin_core;
            document.getElementById('block-height').textContent = btc.blocks ? btc.blocks.toLocaleString() : '-';
            document.getElementById('chain-type').textContent = btc.chain || '-';
            document.getElementById('sync-progress').textContent = btc.verification_progress ? (btc.verification_progress * 100).toFixed(2) + '%' : '-';
        }

        document.getElementById('api-status').textContent = 'Online';

        // Update Fulcrum status
        if (health.components && health.components.fulcrum) {
            const fulcrum = health.components.fulcrum;
            const el = document.getElementById('fulcrum-status');
            const warningEl = document.getElementById('fulcrum-warning');

            if (fulcrum.status === 'connected') {
                el.textContent = 'Connected';
                el.style.color = 'var(--accent-green)';
                if (warningEl) warningEl.style.display = 'none';
            } else if (fulcrum.status === 'degraded') {
                el.textContent = 'Degraded';
                el.style.color = 'var(--accent-orange)';
                if (warningEl) {
                    warningEl.style.display = 'block';
                    warningEl.textContent = '⚠️ Verbose mode not working - restart Fulcrum or wait a few seconds';
                }
            } else if (fulcrum.status === 'not_configured') {
                el.textContent = 'Not configured';
                el.style.color = 'var(--text-secondary)';
                if (warningEl) warningEl.style.display = 'none';
            } else {
                el.textContent = 'Offline';
                el.style.color = 'var(--accent-orange)';
                if (warningEl) warningEl.style.display = 'none';
            }
        }
    } catch (e) {
        document.getElementById('status-dot').classList.add('disconnected');
        document.getElementById('status-text').textContent = 'Bitcoin Node: Disconnected';
        document.getElementById('api-status').textContent = 'Offline';
    }
}

/**
 * Initialize application on DOM ready
 */
function initApp() {
    // Initialize UI components
    initDonationAddress();
    initTooltips();
    initModals();
    initVisualizationModal();

    // Check health immediately and every 30 seconds
    checkHealth();
    setInterval(checkHealth, 30000);

    console.log('ChainForensics initialized');
}

// Expose functions globally for onclick handlers in HTML
// This is necessary because HTML onclick attributes expect global functions
window.toggleSection = toggleSection;
window.copyToClipboard = copyToClipboard;
window.copyAddress = copyAddress;
window.openDonationModal = openDonationModal;
window.closeDonationModal = closeDonationModal;

// Tool functions
window.runKYCPrivacyCheck = runKYCPrivacyCheck;
window.toggleRiskIntelligence = toggleRiskIntelligence;
window.detectCluster = detectCluster;
window.analyzeExchangeProximity = analyzeExchangeProximity;
window.analyzeUTXOPrivacy = analyzeUTXOPrivacy;
window.analyzeTransaction = analyzeTransaction;
window.traceUTXO = traceUTXO;
window.detectCoinJoin = detectCoinJoin;
window.calculatePrivacy = calculatePrivacy;
window.validateAddress = validateAddress;
window.getAddressInfo = getAddressInfo;
window.checkDustAttack = checkDustAttack;
window.loadLabels = loadLabels;

// Visualization functions
window.openVisualization = openVisualization;
window.closeVisualization = closeVisualization;
window.visZoomIn = visZoomIn;
window.visZoomOut = visZoomOut;
window.visFitAll = visFitAll;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
