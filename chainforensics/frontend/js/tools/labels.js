/**
 * Address Label Manager
 * View, add, edit, and delete address labels
 */

import { apiCall } from '../api.js';
import { showLoading, showError } from '../ui.js';
import { createTruncatedValue } from '../utils.js';

let allLabels = [];
let editingAddress = null;

/**
 * Load and display all address labels
 */
export async function loadLabels() {
    showLoading();
    try {
        const result = await apiCall('/addresses/labels?limit=200');
        allLabels = result.labels || [];
        renderLabels();
    } catch (e) {
        showError(e.message);
    }
}

/**
 * Get category color
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
 * Get category badge
 */
function getCategoryBadge(category) {
    const color = getCategoryColor(category);
    const label = category.charAt(0).toUpperCase() + category.slice(1);
    return '<span style="background: ' + color + '; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">' + label + '</span>';
}

/**
 * Render all labels
 */
function renderLabels() {
    let html = '<div class="card">';
    html += '<div class="card-header">';
    html += '<div class="card-title">📝 Address Labels</div>';
    html += '<button id="add-new-label-btn" style="background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue)); border: none; padding: 8px 16px; border-radius: 6px; color: white; font-weight: 600; cursor: pointer;">+ Add New Label</button>';
    html += '</div>';
    html += '<div class="card-body">';

    if (allLabels.length === 0) {
        html += '<div style="text-align: center; padding: 40px; color: var(--text-secondary);">';
        html += '<div style="font-size: 3rem; margin-bottom: 16px;">📝</div>';
        html += '<div style="font-size: 1.1rem; margin-bottom: 8px;">No Labels Yet</div>';
        html += '<div style="font-size: 0.875rem;">Create labels to organize and categorize Bitcoin addresses</div>';
        html += '</div>';
    } else {
        // Filter and search options
        html += '<div style="display: flex; gap: 12px; margin-bottom: 16px;">';
        html += '<input type="text" id="search-labels" placeholder="Search labels or addresses..." style="flex: 1; padding: 8px; border-radius: 6px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);" />';
        html += '<select id="filter-category" style="padding: 8px; border-radius: 6px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);">';
        html += '<option value="">All Categories</option>';
        html += '<option value="personal">Personal</option>';
        html += '<option value="exchange">Exchange</option>';
        html += '<option value="merchant">Merchant</option>';
        html += '<option value="mixer">Mixer</option>';
        html += '<option value="other">Other</option>';
        html += '</select>';
        html += '</div>';

        // Labels table
        html += '<div style="overflow-x: auto;">';
        html += '<table class="io-table">';
        html += '<thead><tr>';
        html += '<th>Address</th>';
        html += '<th>Label</th>';
        html += '<th>Category</th>';
        html += '<th>Notes</th>';
        html += '<th>Updated</th>';
        html += '<th>Actions</th>';
        html += '</tr></thead>';
        html += '<tbody id="labels-tbody">';

        for (var i = 0; i < allLabels.length; i++) {
            html += renderLabelRow(allLabels[i], i);
        }

        html += '</tbody></table>';
        html += '</div>';

        // Summary
        html += '<div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-color); color: var(--text-secondary); font-size: 0.875rem;">';
        html += 'Total: ' + allLabels.length + ' label' + (allLabels.length !== 1 ? 's' : '');
        html += '</div>';
    }

    html += '</div></div>';
    document.getElementById('results-container').innerHTML = html;

    // Attach event listeners
    const addBtn = document.getElementById('add-new-label-btn');
    if (addBtn) {
        addBtn.addEventListener('click', showAddLabelForm);
    }

    const searchInput = document.getElementById('search-labels');
    if (searchInput) {
        searchInput.addEventListener('input', filterLabels);
    }

    const filterSelect = document.getElementById('filter-category');
    if (filterSelect) {
        filterSelect.addEventListener('change', filterLabels);
    }

    // Attach edit and delete buttons
    attachLabelActions();
}

/**
 * Render a single label row
 */
function renderLabelRow(label, index) {
    var updatedDate = label.updated_at ? new Date(label.updated_at).toLocaleDateString() : '-';
    var notesPreview = label.notes ? (label.notes.length > 50 ? label.notes.substring(0, 50) + '...' : label.notes) : '-';

    var html = '<tr data-index="' + index + '">';
    html += '<td class="mono" style="font-size: 0.75rem;">' + createTruncatedValue(label.address, label.address.substring(0, 12) + '...', 'label-addr-' + index) + '</td>';
    html += '<td><strong>' + escapeHtml(label.label) + '</strong></td>';
    html += '<td>' + getCategoryBadge(label.category) + '</td>';
    html += '<td style="font-size: 0.85rem; color: var(--text-secondary);">' + escapeHtml(notesPreview) + '</td>';
    html += '<td style="font-size: 0.85rem; color: var(--text-secondary);">' + updatedDate + '</td>';
    html += '<td>';
    html += '<button class="edit-label-btn" data-address="' + label.address + '" style="background: transparent; border: 1px solid var(--accent-blue); padding: 4px 12px; border-radius: 4px; color: var(--accent-blue); cursor: pointer; margin-right: 4px; font-size: 0.8rem;">Edit</button>';
    html += '<button class="delete-label-btn" data-address="' + label.address + '" style="background: transparent; border: 1px solid var(--accent-red); padding: 4px 12px; border-radius: 4px; color: var(--accent-red); cursor: pointer; font-size: 0.8rem;">Delete</button>';
    html += '</td>';
    html += '</tr>';
    return html;
}

/**
 * Attach event listeners to edit and delete buttons
 */
function attachLabelActions() {
    const editBtns = document.querySelectorAll('.edit-label-btn');
    editBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const address = this.getAttribute('data-address');
            editLabel(address);
        });
    });

    const deleteBtns = document.querySelectorAll('.delete-label-btn');
    deleteBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const address = this.getAttribute('data-address');
            deleteLabel(address);
        });
    });
}

/**
 * Filter labels based on search and category
 */
function filterLabels() {
    const searchTerm = document.getElementById('search-labels').value.toLowerCase();
    const category = document.getElementById('filter-category').value;

    const tbody = document.getElementById('labels-tbody');
    if (!tbody) return;

    let html = '';
    let visibleCount = 0;

    for (var i = 0; i < allLabels.length; i++) {
        const label = allLabels[i];

        // Apply filters
        const matchesSearch = !searchTerm ||
            label.label.toLowerCase().includes(searchTerm) ||
            label.address.toLowerCase().includes(searchTerm) ||
            (label.notes && label.notes.toLowerCase().includes(searchTerm));

        const matchesCategory = !category || label.category === category;

        if (matchesSearch && matchesCategory) {
            html += renderLabelRow(label, i);
            visibleCount++;
        }
    }

    if (visibleCount === 0) {
        html = '<tr><td colspan="6" style="text-align: center; padding: 40px; color: var(--text-secondary);">No matching labels found</td></tr>';
    }

    tbody.innerHTML = html;
    attachLabelActions();
}

/**
 * Show add label form
 */
function showAddLabelForm() {
    editingAddress = null;
    showLabelForm(null);
}

/**
 * Edit existing label
 */
function editLabel(address) {
    const label = allLabels.find(l => l.address === address);
    if (!label) {
        alert('Label not found');
        return;
    }
    editingAddress = address;
    showLabelForm(label);
}

/**
 * Show label form (for add or edit)
 */
function showLabelForm(label) {
    const isEdit = label !== null;

    let html = '<div class="card">';
    html += '<div class="card-header">';
    html += '<div class="card-title">' + (isEdit ? '✏️ Edit Label' : '➕ Add New Label') + '</div>';
    html += '</div>';
    html += '<div class="card-body">';

    html += '<div style="max-width: 600px; margin: 0 auto;">';

    // Address input
    html += '<div style="margin-bottom: 16px;">';
    html += '<label style="display: block; margin-bottom: 4px; font-weight: 600;">Bitcoin Address</label>';
    html += '<input type="text" id="label-address" placeholder="bc1q..." value="' + (label ? escapeHtml(label.address) : '') + '" ' + (isEdit ? 'disabled' : '') + ' style="width: 100%; padding: 10px; border-radius: 6px; border: 1px solid var(--border-color); background: ' + (isEdit ? 'var(--bg-secondary)' : 'var(--bg-tertiary)') + '; color: var(--text-primary);" />';
    if (isEdit) {
        html += '<div style="margin-top: 4px; font-size: 0.75rem; color: var(--text-secondary);">Address cannot be changed when editing</div>';
    }
    html += '</div>';

    // Label name
    html += '<div style="margin-bottom: 16px;">';
    html += '<label style="display: block; margin-bottom: 4px; font-weight: 600;">Label Name</label>';
    html += '<input type="text" id="label-name" placeholder="e.g., My Cold Wallet" value="' + (label ? escapeHtml(label.label) : '') + '" style="width: 100%; padding: 10px; border-radius: 6px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);" />';
    html += '</div>';

    // Category
    html += '<div style="margin-bottom: 16px;">';
    html += '<label style="display: block; margin-bottom: 4px; font-weight: 600;">Category</label>';
    html += '<select id="label-category" style="width: 100%; padding: 10px; border-radius: 6px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary);">';
    var categories = ['personal', 'exchange', 'merchant', 'mixer', 'other'];
    var currentCategory = label ? label.category : 'personal';
    for (var c = 0; c < categories.length; c++) {
        var selected = categories[c] === currentCategory ? ' selected' : '';
        html += '<option value="' + categories[c] + '"' + selected + '>' + categories[c].charAt(0).toUpperCase() + categories[c].slice(1) + '</option>';
    }
    html += '</select>';
    html += '</div>';

    // Notes
    html += '<div style="margin-bottom: 24px;">';
    html += '<label style="display: block; margin-bottom: 4px; font-weight: 600;">Notes <span style="opacity: 0.6; font-weight: normal;">(optional)</span></label>';
    html += '<textarea id="label-notes" placeholder="Additional notes about this address..." rows="4" style="width: 100%; padding: 10px; border-radius: 6px; border: 1px solid var(--border-color); background: var(--bg-tertiary); color: var(--text-primary); resize: vertical;">' + (label && label.notes ? escapeHtml(label.notes) : '') + '</textarea>';
    html += '</div>';

    // Buttons
    html += '<div style="display: flex; gap: 12px;">';
    html += '<button id="save-label-form-btn" style="flex: 1; background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue)); border: none; padding: 12px 24px; border-radius: 6px; color: white; font-weight: 600; cursor: pointer;">💾 ' + (isEdit ? 'Update' : 'Save') + ' Label</button>';
    html += '<button id="cancel-label-form-btn" style="background: transparent; border: 1px solid var(--border-color); padding: 12px 24px; border-radius: 6px; color: var(--text-secondary); font-weight: 600; cursor: pointer;">Cancel</button>';
    html += '</div>';

    html += '</div></div></div>';

    document.getElementById('results-container').innerHTML = html;

    // Attach event listeners
    document.getElementById('save-label-form-btn').addEventListener('click', saveLabelForm);
    document.getElementById('cancel-label-form-btn').addEventListener('click', loadLabels);
}

/**
 * Save label from form
 */
async function saveLabelForm() {
    const address = editingAddress || document.getElementById('label-address').value.trim();
    const labelName = document.getElementById('label-name').value.trim();
    const category = document.getElementById('label-category').value;
    const notes = document.getElementById('label-notes').value.trim();

    if (!address) {
        alert('Please enter a Bitcoin address');
        return;
    }

    if (!labelName) {
        alert('Please enter a label name');
        return;
    }

    try {
        await apiCall('/addresses/labels', {
            address: address,
            label: labelName,
            category: category,
            notes: notes || null
        }, 'POST');

        // Show success and reload
        loadLabels();
    } catch (e) {
        alert('Failed to save label: ' + e.message);
    }
}

/**
 * Delete label
 */
async function deleteLabel(address) {
    const label = allLabels.find(l => l.address === address);
    if (!label) {
        alert('Label not found');
        return;
    }

    if (!confirm('Delete label "' + label.label + '" for address ' + address.substring(0, 20) + '...?')) {
        return;
    }

    try {
        await apiCall('/addresses/labels/' + address, {}, 'DELETE');
        loadLabels();
    } catch (e) {
        alert('Failed to delete label: ' + e.message);
    }
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
