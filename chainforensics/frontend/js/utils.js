/**
 * Utility Functions Module
 * Common helper functions used across the application
 */

import { DONATION_ADDRESS } from './config.js';

/**
 * Format BTC amount with proper decimal places
 * @param {number} btc - Bitcoin amount
 * @returns {string} Formatted BTC string
 */
export function formatBTC(btc) {
    return btc ? btc.toFixed(8) : '0';
}

/**
 * Create a truncated value display with copy button
 * @param {string} fullValue - Full value to copy
 * @param {string} truncatedDisplay - Shortened display text
 * @param {string} uniqueId - Unique identifier for the copy button
 * @returns {string} HTML string with truncated value and copy button
 */
export function createTruncatedValue(fullValue, truncatedDisplay, uniqueId) {
    return '<span class="truncated-value" title="' + fullValue + '">' + truncatedDisplay + '</span>' +
           '<button class="copy-btn-inline" id="copy-' + uniqueId + '" onclick="window.copyToClipboard(\'' + fullValue + '\', \'copy-' + uniqueId + '\')">📋</button>';
}

/**
 * Copy text to clipboard with visual feedback
 * @param {string} text - Text to copy
 * @param {string} buttonId - Button ID for visual feedback
 */
export function copyToClipboard(text, buttonId) {
    navigator.clipboard.writeText(text).then(function() {
        const btn = document.getElementById(buttonId);
        if (btn) {
            btn.classList.add('copied');
            btn.textContent = '✓';
            setTimeout(function() {
                btn.classList.remove('copied');
                btn.textContent = '📋';
            }, 2000);
        }
    }).catch(function(err) {
        console.error('Copy failed:', err);
    });
}

/**
 * Copy donation address with visual feedback
 */
export function copyAddress() {
    navigator.clipboard.writeText(DONATION_ADDRESS).then(function() {
        const btn = document.getElementById('copy-btn');
        btn.classList.add('copied');
        btn.innerHTML = '✓ Copied!';
        setTimeout(function() {
            btn.classList.remove('copied');
            btn.innerHTML = '📋 Copy Address';
        }, 2000);
    });
}

/**
 * Toggle sidebar section collapse
 * @param {string} sectionId - ID of the section to toggle
 */
export function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.toggle('collapsed');
    }
}
