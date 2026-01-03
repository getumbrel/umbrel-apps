/**
 * UI Helper Functions Module
 * Functions for managing UI state, loading indicators, modals, etc.
 */

import { DONATION_ADDRESS } from './config.js';

/**
 * Show loading indicator in results container
 * @param {string} msg - Loading message (optional)
 */
export function showLoading(msg) {
    msg = msg || 'Loading...';
    document.getElementById('results-container').innerHTML =
        '<div class="card"><div class="card-body"><div class="loading"><div class="spinner"></div>' + msg + '</div></div></div>';
}

/**
 * Hide loading indicator
 */
export function hideLoading() {
    // Loading is hidden by replacing content in results-container
}

/**
 * Show error message in results container
 * @param {string} msg - Error message
 */
export function showError(msg) {
    document.getElementById('results-container').innerHTML =
        '<div class="card"><div class="card-body"><p style="color: var(--accent-red); text-align: center; padding: 40px;">❌ Error: ' + msg + '</p></div></div>';
}

/**
 * Open donation modal
 */
export function openDonationModal() {
    document.getElementById('donation-modal').classList.add('active');
}

/**
 * Close donation modal
 */
export function closeDonationModal() {
    document.getElementById('donation-modal').classList.remove('active');
}

/**
 * Initialize tooltip positioning
 */
export function initTooltips() {
    // Dynamic tooltip positioning
    document.querySelectorAll('.help-icon').forEach(function(icon) {
        icon.addEventListener('mouseenter', function(e) {
            var tooltip = this.querySelector('.tooltip');
            if (tooltip) {
                var rect = this.getBoundingClientRect();
                var tooltipWidth = 280;
                var tooltipHeight = tooltip.offsetHeight || 100;

                // Position to the right of the icon
                var left = rect.right + 8;
                var top = rect.top + (rect.height / 2) - (tooltipHeight / 2);

                // If tooltip would go off right edge, position to the left
                if (left + tooltipWidth > window.innerWidth - 20) {
                    left = rect.left - tooltipWidth - 8;
                }

                // Keep tooltip within vertical bounds
                if (top < 10) top = 10;
                if (top + tooltipHeight > window.innerHeight - 10) {
                    top = window.innerHeight - tooltipHeight - 10;
                }

                tooltip.style.left = left + 'px';
                tooltip.style.top = top + 'px';
            }
        });
    });
}

/**
 * Initialize modal event listeners
 */
export function initModals() {
    // Close donation modal on background click
    document.getElementById('donation-modal').addEventListener('click', function(e) {
        if (e.target.id === 'donation-modal') closeDonationModal();
    });

    // Close modals on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeDonationModal();
            // Visualization modal close is handled in visualization.js
        }
    });
}

/**
 * Initialize donation address display
 */
export function initDonationAddress() {
    document.getElementById('donation-address').textContent = DONATION_ADDRESS;
}
