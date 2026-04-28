import { relayInit } from "nostr-tools";
import "websocket-polyfill"; // polyfill for relayInit in nodejs
import pRetry from "p-retry";

import { readIdentifierFromFile, writeIdentifierToFile, deleteStoreFile, getPublicKeyAndRelaysFromIdentifier } from "./helpers.js";
import { LOCAL_RELAY_URL, DISCOVERY_STATUS } from "./constants.js";

/*
Relay discovery and connection logic is as follows:
1. Await connection to local nostr-rs-relay
2. Connect to relays from NIP-05, or from a list of popular relays if only an npub is provided
  - retry connection attempts indefinitely, with exponential backoff to max timeout of 1 hour
3. Subscribe to events
  - Publish events to local nostr-rs-relay
  - If a Kind 3 Contact List event is received, connect to any new relays in that list that we are not already connected to and subscribe to events from those relays
  - Periodically close any relays that are not in the most recent Kind 3 Contact List Event
*/

class RelayManager {
  constructor() {
    this.resetState();
    this.establishRelayConnections();
  }

  resetState() {
    this.relays = {};
    // latestRelays tracks relays from the most recent Kind 3 Contact List Event (or default relays if no Kind 3 Contact List Events have been received)
    this.latestRelays = null; // { relays, timestamp }
    this.identifier = null; // store to avoid having to read from file for getConnectionStatus
    this.pubkey = null; // hex formatted pubkey
    this.status = DISCOVERY_STATUS.IDLE;
    this.firstEventReceived = false;
    if (this.cleanUpRelaysInterval) {
      clearInterval(this.cleanUpRelaysInterval);
      this.cleanUpRelaysInterval = null;
    }
  }

  // ===============================
  // Connection Methods
  // ===============================

  async establishRelayConnections() {
    // We await successful connection to local nostr-rs-relay or else events from public relays will not be published to the local relay
    try {
      this.localRelay = await this.initializeRelay(LOCAL_RELAY_URL, { isPrivate: true });
    } catch (error) {
      console.log(error?.message); // thrown by initializeRelay after all retry attempts have failed
      return;
    }
    // Connect to public relays discovered from NIP-05 or npub
    this.discoverAndConnectToRelays();
  }

  async initializeRelay(url, options = {}) {
    const isPrivate = options.isPrivate || false;

    const relay = relayInit(url);

    // we only add a relay to the this.relays object if it is not the user's local nostr-rs-relay
    // this is done before we return the connectionPromise so that we can check if the relay is already being initialized when new Kind 3 Contact List events are received, even if the relay is not yet connected
    if (!isPrivate) {
      this.relays[url] = relay;
    }

    relay.on("connect", () => console.log(`Connected to ${relay.url}`));

    // connectRelay returns a promise that resolves when the relay connects or rejects when the relay fails to connect
    // so that we can use p-retry to retry connection attempts with exponential backoff.
    const connectRelay = () => {
      // error objects do not seem to ever be passed to relay.connect or the on error event handler
      return new Promise((resolve, reject) => {
        relay.connect()
        .then(resolve)
        .catch(error => {
            reject(error || new Error(`Connection to ${relay.url} failed without an error object.`));
          });

        relay.on('error', error => {
          reject(error || new Error(`Error event from ${relay.url} without an error object.`));
        });
      });
    };

    // abortController is used to abort the p-retry connection attempts if the relay is removed from this.relays object while the connection attempt is in progress
    // this would occur if cleanup of old relays occured while a connection attempt was in progress
    const abortController = new AbortController();

    try {
      await pRetry(connectRelay, {
        forever: true, // retry forever or until abortController.abort is called
        maxTimeout: 1000 * 60 * 60, // max timeout between retries is 1 hour
        signal: abortController.signal,
        onFailedAttempt: error => {
          console.log (`Attempt ${error.attemptNumber} to connect to ${relay.url} failed.`);

          // we do not abort for our local relay
          if (!isPrivate && !this.relays[url]) {
            abortController.abort(`Additional connection attempts to ${relay.url} aborted because relay is no longer in user's Kind 3 Contact List.`);
          }

        },
      });
    } catch (error) {
      console.log(error.message);
      throw new Error(`All attempts to connect to ${relay.url} have failed. No further attempts will be made.`);
    }

    return relay;
  }

  async discoverAndConnectToRelays() {
    if (this.cleanUpRelaysInterval) {
      clearInterval(this.cleanUpRelaysInterval);
    }

    const identifierData = await readIdentifierFromFile();
    // we return early if there is no identifier set
    if (!identifierData) return;

    this.identifier = identifierData.identifier;
    console.log(`NIP-05/NIP-19 Identifier: ${this.identifier}`);

    this.status = DISCOVERY_STATUS.DISCOVERING_RELAYS;

    const { pubkey, relays } = await getPublicKeyAndRelaysFromIdentifier(this.identifier);
    this.pubkey = pubkey;
    this.latestRelays = { relays, timestamp: 0 };

    for (const url of relays) {
      this.connectAndSubscribeToRelay(url);
    }

    // Clean up relays that are not in the most recent Kind 3 Contact List Event every hour
    this.cleanUpRelaysInterval = setInterval(() => {
      this.removeOutdatedRelays();
    }, 60 * 60 * 1000);
  }

  async connectAndSubscribeToRelay(url) {
    // We ignore all unencrypted relays (beginning with 'ws://') as a way to filter out
    // a user's local nostr-rs-relay, which could be added to their clients or NIP-05.
    // This is a provisional measure, given the vast array of URLs that might be used,
    // including Tailscale magicDNS, local network domain name, IP address, etc.
    // This approach caters to the majority of use cases.
    if (url.startsWith("ws://")) return;

    // we return early if the relay is currently being, or already is, initialized
    if (this.relays[url]) return;

    try {
      const relay = await this.initializeRelay(url);
      if (relay) {
        const sub = relay.sub([{ authors: [this.pubkey] }]);
        sub.on('event', event => this.handleEvent(event, relay));
      }
    } catch (error) {
      console.error(error?.message);
    }
  }

  // ===============================
  // Event Handling Methods
  // ===============================

  handleEvent(event, relay) {
    if (this.status === DISCOVERY_STATUS.DISCOVERING_RELAYS) {
      this.status = DISCOVERY_STATUS.IDLE;
    }

    // we set firstEventReceived to true after receiving the first event from a public relay so that we can show the SyncConfirmationModal ASAP in the UI
    if (!this.firstEventReceived) {
      this.firstEventReceived = true;
    }

    // If a Kind 3 Contact List event is received with a newer created_at timestamp, we connect to any new relays in that list
    // that we are not already connected to and subscribe to events from those relays
    if (event.kind === 3) {
      if (this.latestRelays === null || event.created_at > this.latestRelays.timestamp) {
        console.log(`A more recent Kind 3 event was received from ${relay.url} with date: ${event.created_at}`);
        this.latestRelays = { relays: event.content, timestamp: event.created_at };
        const newRelays = Object.keys(JSON.parse(event.content));
        for (const url of newRelays) {
          this.connectAndSubscribeToRelay(url);
        }
      }
    }

    try {
      this.localRelay.publish(event);
    } catch (error) {
      console.error('Error publishing to local relay:', error);
    }
  }

  // =====================
  // Relay Management Methods
  // =====================

  removeOutdatedRelays() {
    // Fix: getPublicKeyAndRelaysFromIdentifier returns an array for npub identifiers,
    // so this.latestRelays.relays may be an array (initial state) or a JSON string
    // (after a Kind 3 Contact List event is received). JSON.parse(array) throws a
    // SyntaxError, causing the relay-proxy to crash 60 minutes after startup when
    // the cleanup interval first fires.
    let latestRelays = [];
    try {
      if (this.latestRelays && typeof this.latestRelays.relays === 'string' && this.latestRelays.relays) {
        latestRelays = Object.keys(JSON.parse(this.latestRelays.relays));
      } else if (Array.isArray(this.latestRelays?.relays)) {
        latestRelays = this.latestRelays.relays;
      }
    } catch (e) { /* ignore parse errors */ }
    const relaysToRemove = Object.keys(this.relays).filter(url => !latestRelays.includes(url));
    if (relaysToRemove.length > 0) {
      console.log(`Removing outdated relays: ${relaysToRemove}`);
    }

    for (const url of relaysToRemove) {
      this.closeRelay(url);
    }
  }

  closeRelay(url) {
    const relay = this.relays[url];
    try {
      relay.close();
      delete this.relays[url];
      console.log(`${url} connection closed`);
    } catch (error) {
      console.log(`Error closing ${url}`);
    }
  }

  getConnectionStatus() {
    /* 
    'web socket readyState values are:
      - 0: CONNECTING
      - 1: OPEN
      - 2: CLOSING
      - 3: CLOSED
    */

    // we map relayStates to an array of objects with url and readyState properties, while filtering out relays that may cause errors.
    const relayStates = Object.entries(this.relays).map(([key, relay]) => {
      if (relay.url && relay.status) {
        return {
          url: relay.url,
          readyState: relay.status, // this is a getter
        };
      } else {
        return null;
      }
    }).filter(state => state !== null);

    return { identifier: this.identifier, status: this.status, firstEventReceived: this.firstEventReceived, relayStates };
  }

  // ==========================
  // NIP-05/NIP-19 Identifier Management Methods
  // ==========================

  async addIdentifier(identifier) {
    await writeIdentifierToFile(identifier);
    this.discoverAndConnectToRelays();
  }

  async removeIdentifier() {
    await deleteStoreFile();
    for (const url of Object.keys(this.relays)) {
      this.closeRelay(url);
    }
    this.resetState();
  }
}

export default RelayManager;
