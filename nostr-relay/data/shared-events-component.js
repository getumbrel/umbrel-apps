/**
 * Shared Recent Events Component
 * Used by both the public relay page (nostr.janx.com) and admin dashboard (janx.local:4848)
 * Provides event rendering, kind-to-NIP mapping, and common event utilities
 */

// Kind-to-NIP mapping
const KIND_TO_NIP_MAP = {
  // Kind 0: User profile
  0: "NIP-05",
  // Kind 1: Text note
  1: "NIP-01",
  // Kind 2: Recommend server
  2: "NIP-01",
  // Kind 3: Contacts
  3: "NIP-02",
  // Kind 4: Encrypted private message
  4: "NIP-04",
  // Kind 5: Event deletion
  5: "NIP-09",
  // Kind 6: Repost
  6: "NIP-18",
  // Kind 7: Reaction
  7: "NIP-25",
  // Kind 8: Badge award
  8: "NIP-58",
  // Kind 10: Mute list
  10: "NIP-51",
  // Kind 11: Pinned list
  11: "NIP-51",
  // Kind 12: Community post approval
  12: "NIP-72",
  // Kind 13: Note taken
  13: "NIP-23",
  // Kind 14: Directory list
  14: "NIP-51",
  // Kind 15: Search result set
  15: "NIP-50",
  // Kind 16: Authentication
  16: "NIP-42",
  // Kind 19: Community moderation event
  19: "NIP-72",
  // Kind 20: Create or update a community
  20: "NIP-72",
  // Kind 21: Create or update a community moderation policy
  21: "NIP-72",
  // Kind 22: Create or update a community list
  22: "NIP-72",
  // Kind 23: Long-form content
  23: "NIP-23",
  // Kind 24: Long-form draft
  24: "NIP-23",
  // Kind 25: Event status
  25: "NIP-XX",
  // Kind 27: Expense report
  27: "NIP-XX",
  // Kind 30: Categorized people
  30: "NIP-51",
  // Kind 31: Categorized bookmarks
  31: "NIP-51",
  // Kind 40: Channel creation
  40: "NIP-28",
  // Kind 41: Channel metadata
  41: "NIP-28",
  // Kind 42: Channel message
  42: "NIP-28",
  // Kind 43: Channel hide message
  43: "NIP-28",
  // Kind 44: Channel mute user
  44: "NIP-28",
  // Kind 45: Public chat message
  45: "NIP-XX",
  // Kind 50: Chat message
  50: "NIP-24",
  // Kind 51: Chat channels list
  51: "NIP-51",
  // Kind 53: Live chat message
  53: "NIP-XX",
  // Kind 55: Auction announcement
  55: "NIP-XX",
  // Kind 56: Auction bid
  56: "NIP-XX",
  // Kind 57: Lightning invoice
  57: "NIP-57",
  // Kind 58: Badge definition
  58: "NIP-58",
  // Kind 59: Badge award
  59: "NIP-58",
  // Kind 60: Event reporting
  60: "NIP-56",
  // Kind 61: Zap goal
  61: "NIP-75",
  // Kind 64: Note activity summary
  64: "NIP-XX",
  // Kind 65: Reporting
  65: "NIP-56",
  // Kind 99: Classification
  99: "NIP-XX",
  // Kind 1000+: Parameterized replaceable events
  1000: "NIP-33",
  1059: "NIP-59",
  1063: "NIP-94",
  1311: "NIP-XX",
  3036: "NIP-XX",
  5000: "NIP-XX",
  6000: "NIP-XX",
  10000: "NIP-51",
  10001: "NIP-51",
  10002: "NIP-65",
  10005: "NIP-51",
  10015: "NIP-51",
  10030: "NIP-51",
  10096: "NIP-XX",
  13194: "NIP-XX",
  14146: "NIP-XX",
  15128: "NIP-XX",
  20000: "NIP-XX",
  30000: "NIP-51",
  30001: "NIP-51",
  30002: "NIP-51",
  30003: "NIP-51",
  30004: "NIP-51",
  30005: "NIP-51",
  30006: "NIP-51",
  30007: "NIP-51",
  30008: "NIP-51",
  30009: "NIP-51",
  30010: "NIP-51",
  30011: "NIP-51",
  30012: "NIP-51",
  30013: "NIP-51",
  30014: "NIP-51",
  30015: "NIP-51",
  30016: "NIP-51",
  30017: "NIP-51",
  30018: "NIP-51",
  30019: "NIP-51",
  30020: "NIP-51",
  30021: "NIP-51",
  30022: "NIP-51",
  30023: "NIP-23",
  30024: "NIP-XX",
  30030: "NIP-XX",
  30040: "NIP-72",
  30041: "NIP-72",
  30078: "NIP-78",
  30315: "NIP-XX",
  30402: "NIP-XX",
  31922: "NIP-XX",
  31923: "NIP-XX",
  31924: "NIP-XX",
  31925: "NIP-XX",
};

/**
 * Convert an event kind number to its NIP identifier
 * @param {number} kind - Event kind number
 * @returns {string} NIP identifier (e.g., "NIP-01", "NIP-04")
 */
function kindToNip(kind) {
  if (typeof kind !== "number" || kind < 0) return "Unknown";
  if (KIND_TO_NIP_MAP[kind]) return KIND_TO_NIP_MAP[kind];
  // Default for unknown kinds
  return "NIP-XX";
}

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} HTML-escaped text
 */
function escapeHtml(text) {
  if (typeof text !== "string") return "";
  const map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return text.replace(/[&<>"']/g, (char) => map[char]);
}

/**
 * Format Unix timestamp to human-readable format
 * @param {number} timestamp - Unix timestamp in seconds
 * @returns {string} Formatted date/time string
 */
function formatTimestamp(timestamp) {
  if (!timestamp || typeof timestamp !== "number") return "Unknown";
  try {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "Invalid";
  }
}

/**
 * Create event row HTML
 * @param {Object} event - Event object with { kind, created_at, content_preview, id_short, pubkey_short }
 * @returns {string} HTML for the event row
 */
function createEventRowHtml(event) {
  if (!event || typeof event !== "object") return "";

  const timestamp = formatTimestamp(event.created_at);
  const kind = event.kind || 0;
  const nip = kindToNip(kind);
  const message = escapeHtml(event.content_preview || "");

  return (
    '<div class="event-row">' +
    '<div class="event-time">' +
    escapeHtml(timestamp) +
    "</div>" +
    '<div class="event-kind">' +
    escapeHtml(String(kind)) +
    "</div>" +
    '<div class="event-kind">' +
    escapeHtml(nip) +
    "</div>" +
    '<div class="event-msg" title="' +
    message +
    '">' +
    message +
    "</div>" +
    "</div>"
  );
}

/**
 * Render multiple event rows
 * @param {Array} events - Array of event objects
 * @param {number} limit - Maximum number of rows to render
 * @returns {string} HTML for all event rows
 */
function renderEventRows(events, limit = 20) {
  if (!Array.isArray(events) || events.length === 0) {
    return '<div class="event-row"><div class="event-msg">No events</div></div>';
  }

  return events
    .slice(0, limit)
    .map((event) => createEventRowHtml(event))
    .join("");
}

/**
 * CSS styles for the shared events component
 * Can be injected into pages that don't already have these styles
 */
const EVENTS_COMPONENT_CSS = `
  .event-row {
    display: grid;
    grid-template-columns: 180px 80px 80px 1fr;
    gap: 12px;
    padding: 12px;
    border-bottom: 1px solid var(--border, #2a2d3a);
    font-size: 13px;
    align-items: center;
  }

  .event-time {
    color: var(--muted, #64748b);
    font-family: "Courier New", monospace;
  }

  .event-kind {
    color: var(--text, #e2e8f0);
    font-family: "Courier New", monospace;
    text-align: center;
  }

  .event-msg {
    color: var(--text, #e2e8f0);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  @media (max-width: 768px) {
    .event-row {
      grid-template-columns: 1fr;
      font-size: 12px;
    }

    .event-time,
    .event-kind,
    .event-msg {
      text-align: left;
    }
  }
`;

// Export functions for use in both pages
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    kindToNip,
    escapeHtml,
    formatTimestamp,
    createEventRowHtml,
    renderEventRows,
    KIND_TO_NIP_MAP,
    EVENTS_COMPONENT_CSS,
  };
}
