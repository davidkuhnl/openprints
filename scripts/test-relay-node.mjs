#!/usr/bin/env node
/**
 * Nostr WebSocket check for the local relay.
 * Sends a REQ for kind-1 and expects EOSE or events.
 *
 * Prerequisites: Node.js with native WebSocket support.
 * Usage: node scripts/test-relay-node.mjs [WS_URL]
 * Example: RELAY_WS_URL=ws://localhost:7447 node scripts/test-relay-node.mjs
 */

const wsUrl = process.env.RELAY_WS_URL || process.argv[2] || 'ws://localhost:7447';

async function main() {
  const WS = globalThis.WebSocket;
  if (!WS) {
    console.error('Node WebSocket API is not available. Use "./scripts/test-relay-ws.sh --python" or upgrade Node.');
    process.exit(1);
  }

  return new Promise((resolve, reject) => {
    const client = new WS(wsUrl);
    const timeout = setTimeout(() => {
      try {
        client.close();
      } catch (_) {
        // no-op
      }
      reject(new Error('Timeout waiting for relay response'));
    }, 5000);

    client.addEventListener('open', () => {
      client.send(JSON.stringify(['REQ', 'openprints-test', { kinds: [1] }]));
    });

    client.addEventListener('message', (event) => {
      const raw = typeof event.data === 'string' ? event.data : String(event.data);
      try {
        const msg = JSON.parse(raw);
        if (Array.isArray(msg) && (msg[0] === 'EOSE' || msg[0] === 'EVENT')) {
          clearTimeout(timeout);
          client.close();
          console.log('Relay responded with:', msg[0]);
          console.log('OK: Nostr WebSocket is working.');
          resolve();
        }
      } catch (_) {
        // non-JSON or other; still proves relay sent something
        clearTimeout(timeout);
        client.close();
        console.log('OK: relay sent a response.');
        resolve();
      }
    });

    client.addEventListener('error', () => {
      clearTimeout(timeout);
      reject(new Error('WebSocket error while talking to relay'));
    });

    client.addEventListener('close', () => {
      clearTimeout(timeout);
    });
  });
}

main().catch((err) => {
  console.error('Failed:', err.message);
  process.exit(1);
});
