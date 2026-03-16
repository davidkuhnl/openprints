import {
  startIdentityStore,
  subscribeToCurrentIdentity,
  type IdentitySnapshot,
} from "~/lib/identity-store";
import { parsePubkey, pubkeysEqual } from "~/lib/pubkey";

const OWNER_EDIT_CTA_SELECTOR = "[data-owner-edit-cta]";

let ownerEditInitialized = false;
let ownerEditUnsubscribe: (() => void) | null = null;

const applyOwnerVisibility = (snapshot: IdentitySnapshot) => {
  const signerPubkey = snapshot.authoritative ? parsePubkey(snapshot.pubkey) : null;
  const ctas = document.querySelectorAll<HTMLElement>(OWNER_EDIT_CTA_SELECTOR);

  for (const cta of ctas) {
    const ownerPubkey = parsePubkey(cta.dataset.ownerPubkey);
    const show = pubkeysEqual(signerPubkey, ownerPubkey);
    cta.classList.toggle("hidden", !show);
    cta.setAttribute("aria-hidden", String(!show));
  }
};

export const initOwnerEditCtas = () => {
  if (typeof window === "undefined") return;
  if (ownerEditInitialized) return;
  ownerEditInitialized = true;

  startIdentityStore();
  ownerEditUnsubscribe = subscribeToCurrentIdentity((snapshot: IdentitySnapshot) => {
    applyOwnerVisibility(snapshot);
  });

  window.addEventListener(
    "beforeunload",
    () => {
      ownerEditUnsubscribe?.();
      ownerEditUnsubscribe = null;
      ownerEditInitialized = false;
    },
    { once: true },
  );
};
