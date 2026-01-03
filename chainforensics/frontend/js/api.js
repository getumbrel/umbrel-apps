/**
 * API Module
 * Wrapper for API calls with error handling
 */

import { API_BASE } from './config.js';

/**
 * Make an API call to the backend
 * @param {string} endpoint - API endpoint path
 * @param {Object} params - Query parameters (for GET) or request body (for POST/PUT/PATCH)
 * @param {string} method - HTTP method (default: 'GET')
 * @returns {Promise<Object>} JSON response
 */
export async function apiCall(endpoint, params, method) {
    params = params || {};
    method = method || 'GET';

    const url = new URL(API_BASE + endpoint);
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };

    // For GET and DELETE, add params as query parameters
    // For POST, PUT, PATCH, add params as request body
    if (method === 'GET' || method === 'DELETE') {
        Object.keys(params).forEach(function(key) {
            if (params[key] !== null && params[key] !== undefined) {
                url.searchParams.append(key, params[key]);
            }
        });
    } else {
        options.body = JSON.stringify(params);
    }

    const response = await fetch(url, options);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'API Error');
    }
    return await response.json();
}
