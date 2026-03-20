import { parsePubkey, type Pubkey } from "~/lib/pubkey";
import { nip19 } from "nostr-tools";

type NostrSignerLike = {
  getPublicKey?: () => Promise<string>;
  signEvent?: (event: unknown) => Promise<unknown>;
};

export type IdentityRecord = {
  id?: string | null;
  pubkey?: Pubkey | null;
  npub?: string | null;
  status?: string | null;
  display_name_resolved?: string | null;
  display_name?: string | null;
  name?: string | null;
  picture?: string | null;
  shape?: string | null;
  nip05?: string | null;
  lud06?: string | null;
  lud16?: string | null;
  lnurl?: string | null;
};

type IdentityCacheEntry = {
  pubkey: Pubkey;
  identity: IdentityRecord | null;
  notFound: boolean;
  cachedAt: number;
};

type CacheSource = "none" | "memory" | "storage" | "backend";
type SignerStatus = "checking" | "confirmed" | "timed_out";

export type IdentitySnapshot = {
  pubkey: Pubkey | null;
  identity: IdentityRecord | null;
  authoritative: boolean;
  signerStatus: SignerStatus;
  source: CacheSource;
  refreshing: boolean;
  updatedAt: number | null;
  resolvedDisplayLabel: string | null;
  resolvedNpub: string | null;
};

type CurrentIdentitySubscriber = (snapshot: IdentitySnapshot) => void;
type IdentitySubscriber = (snapshot: IdentitySnapshot) => void;

type MemoryIdentityEntry = {
  identity: IdentityRecord | null;
  notFound: boolean;
  fetchedAt: number;
  source: CacheSource;
};

type GetCurrentPubkeyOptions = {
  allowCache?: boolean;
};

type GetCurrentIdentityOptions = {
  allowCache?: boolean;
};

type SignWithCurrentSignerOptions = {
  requirePubkeyMatch?: boolean;
};

const STORAGE_IDENTITY_PREFIX = "openprints:identity:";
const STORAGE_LAST_PUBKEY_KEY = "openprints:lastPubkey";
const MEMORY_TTL_MS = 45_000;
const STORAGE_TTL_MS = 4 * 60_000;
const SIGNER_TIMEOUT_MS = 1_800;
const SIGNER_GIVE_UP_MS = 10_000;
const MIN_RECONCILE_GAP_MS = 1_200;
const SIGNER_RECONCILE_INTERVAL_MS = 5_000;

const memoryByPubkey = new Map<Pubkey, MemoryIdentityEntry>();
const currentSubscribers = new Set<CurrentIdentitySubscriber>();
const subscribersByPubkey = new Map<Pubkey, Set<IdentitySubscriber>>();
const refreshInFlightByPubkey = new Map<Pubkey, Promise<IdentityRecord | null>>();

let started = false;
let reconciling = false;
let lastReconcileAt = 0;
let activePubkey: Pubkey | null = null;
let activeAuthoritative = false;
let activeRefreshing = false;
let signerStatus: SignerStatus = "checking";
let signerWaitStartedAt: number | null = null;

const getSigner = (): NostrSignerLike | null => {
  if (typeof window === "undefined") return null;
  const w = window as Window & { nostr?: NostrSignerLike };
  return w.nostr ?? null;
};

const truncateHexPubkey = (pubkey: Pubkey): string => `${pubkey.slice(0, 10)}...${pubkey.slice(-6)}`;
const truncateNpub = (npub: string): string =>
  npub.length > 18 ? `${npub.slice(0, 10)}...${npub.slice(-6)}` : npub;

const resolveNpub = (pubkey: Pubkey, identity: IdentityRecord | null): string | null => {
  const identityNpub = identity?.npub?.trim();
  if (identityNpub) return identityNpub;
  try {
    return nip19.npubEncode(pubkey);
  } catch {
    return null;
  }
};

const resolveDisplayLabel = (pubkey: Pubkey, identity: IdentityRecord | null, npub: string | null) => {
  const resolved =
    identity?.display_name_resolved?.trim() ||
    identity?.display_name?.trim() ||
    identity?.name?.trim();
  if (resolved) return resolved;
  if (npub) return truncateNpub(npub);
  return truncateHexPubkey(pubkey);
};

const isMemoryFresh = (entry: MemoryIdentityEntry | undefined): boolean => {
  if (!entry) return false;
  return Date.now() - entry.fetchedAt < MEMORY_TTL_MS;
};

const isStorageFresh = (entry: IdentityCacheEntry | null): boolean => {
  if (!entry) return false;
  return Date.now() - entry.cachedAt < STORAGE_TTL_MS;
};

const getSnapshotForPubkey = (pubkey: Pubkey | null): IdentitySnapshot => {
  if (!pubkey) {
    return {
      pubkey: null,
      identity: null,
      authoritative: false,
      signerStatus,
      source: "none",
      refreshing: activeRefreshing,
      updatedAt: null,
      resolvedDisplayLabel: null,
      resolvedNpub: null,
    };
  }

  const memoryEntry = memoryByPubkey.get(pubkey);
  const identity = memoryEntry?.notFound ? null : (memoryEntry?.identity ?? null);
  const resolvedNpub = resolveNpub(pubkey, identity);
  const resolvedDisplayLabel = resolveDisplayLabel(pubkey, identity, resolvedNpub);
  return {
    pubkey,
    identity,
    authoritative: activeAuthoritative && activePubkey === pubkey,
    signerStatus,
    source: memoryEntry?.source ?? "none",
    refreshing: activeRefreshing,
    updatedAt: memoryEntry?.fetchedAt ?? null,
    resolvedDisplayLabel,
    resolvedNpub,
  };
};

const emitSnapshot = (pubkey: Pubkey | null) => {
  const snapshot = getSnapshotForPubkey(pubkey);

  for (const callback of currentSubscribers) {
    callback(snapshot);
  }

  if (!pubkey) return;
  const scoped = subscribersByPubkey.get(pubkey);
  if (!scoped) return;
  for (const callback of scoped) {
    callback(snapshot);
  }
};

const emitCurrentIdentityEvent = (snapshot: IdentitySnapshot) => {
  document.dispatchEvent(
    new CustomEvent("openprints-identity-change", {
      detail: snapshot,
    }),
  );
};

const setSignerStatus = (nextStatus: SignerStatus) => {
  if (signerStatus === nextStatus) return;
  signerStatus = nextStatus;
  const snapshot = getSnapshotForPubkey(activePubkey);
  emitSnapshot(activePubkey);
  emitCurrentIdentityEvent(snapshot);
};

const readLastPubkeyFromStorage = (): Pubkey | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_LAST_PUBKEY_KEY);
    return parsePubkey(raw);
  } catch {
    return null;
  }
};

const writeLastPubkeyToStorage = (pubkey: Pubkey) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_LAST_PUBKEY_KEY, pubkey);
  } catch {
    // no-op
  }
};

const readIdentityFromStorage = (pubkey: Pubkey): IdentityCacheEntry | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(`${STORAGE_IDENTITY_PREFIX}${pubkey}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as IdentityCacheEntry;
    if (!parsed || parsePubkey(parsed.pubkey) !== pubkey) return null;
    if (typeof parsed.cachedAt !== "number") return null;
    return {
      pubkey,
      identity: parsed.notFound ? null : (parsed.identity ?? null),
      notFound: Boolean(parsed.notFound),
      cachedAt: parsed.cachedAt,
    };
  } catch {
    return null;
  }
};

const writeIdentityToStorage = (
  pubkey: Pubkey,
  identity: IdentityRecord | null,
  notFound: boolean,
) => {
  if (typeof window === "undefined") return;
  const payload: IdentityCacheEntry = {
    pubkey,
    identity: notFound ? null : identity,
    notFound,
    cachedAt: Date.now(),
  };
  try {
    window.localStorage.setItem(
      `${STORAGE_IDENTITY_PREFIX}${pubkey}`,
      JSON.stringify(payload),
    );
  } catch {
    // no-op
  }
};

const writeMemoryIdentity = (
  pubkey: Pubkey,
  identity: IdentityRecord | null,
  notFound: boolean,
  source: CacheSource,
) => {
  memoryByPubkey.set(pubkey, {
    identity,
    notFound,
    fetchedAt: Date.now(),
    source,
  });
};

const setActivePubkey = (pubkey: Pubkey | null, authoritative: boolean) => {
  activePubkey = pubkey;
  activeAuthoritative = authoritative && Boolean(pubkey);
  if (activeAuthoritative) {
    signerWaitStartedAt = null;
    signerStatus = "confirmed";
  } else if (!activePubkey) {
    signerWaitStartedAt = null;
    signerStatus = "checking";
  }
  const snapshot = getSnapshotForPubkey(activePubkey);
  emitSnapshot(activePubkey);
  emitCurrentIdentityEvent(snapshot);
};

const resolveSignerPubkey = async (): Promise<Pubkey | null> => {
  const signer = getSigner();
  if (!signer || typeof signer.getPublicKey !== "function") return null;
  try {
    const pubkey = await Promise.race([
      signer.getPublicKey(),
      new Promise<string>((_, reject) => {
        window.setTimeout(
          () => reject(new Error("Timed out waiting for signer pubkey")),
          SIGNER_TIMEOUT_MS,
        );
      }),
    ]);
    return parsePubkey(pubkey);
  } catch {
    return null;
  }
};

const getApiBase = (): string => {
  const raw = import.meta.env.PUBLIC_OPENPRINTS_API_URL ?? "";
  return raw ? raw.replace(/\/$/, "") : "";
};

const fetchIdentityFromBackend = async (
  pubkey: Pubkey,
): Promise<{ identity: IdentityRecord | null; notFound: boolean }> => {
  const apiBase = getApiBase();
  if (!apiBase) return { identity: null, notFound: true };

  try {
    const res = await fetch(`${apiBase}/identity/${encodeURIComponent(pubkey)}`, {
      headers: { accept: "application/json" },
    });
    if (res.status === 404) return { identity: null, notFound: true };
    if (!res.ok) return { identity: null, notFound: false };
    const payload = (await res.json()) as IdentityRecord;
    return { identity: payload, notFound: false };
  } catch {
    return { identity: null, notFound: false };
  }
};

const maybeEmitIdentityMetadata = (pubkey: Pubkey, identity: IdentityRecord | null) => {
  const lnurl = identity?.lnurl ?? identity?.lud16 ?? identity?.lud06 ?? null;
  document.dispatchEvent(
    new CustomEvent("openprints-identity-metadata", {
      detail: {
        pubkey,
        lnurl,
      },
    }),
  );
};

export const refreshIdentity = async (rawPubkey: string): Promise<IdentityRecord | null> => {
  const pubkey = parsePubkey(rawPubkey);
  if (!pubkey) return null;

  const existing = refreshInFlightByPubkey.get(pubkey);
  if (existing) return existing;

  const request = (async () => {
    const result = await fetchIdentityFromBackend(pubkey);
    writeMemoryIdentity(pubkey, result.identity, result.notFound, "backend");
    writeIdentityToStorage(pubkey, result.identity, result.notFound);
    maybeEmitIdentityMetadata(pubkey, result.identity);

    if (activePubkey === pubkey) {
      emitSnapshot(pubkey);
      emitCurrentIdentityEvent(getSnapshotForPubkey(pubkey));
    } else {
      const scoped = subscribersByPubkey.get(pubkey);
      if (scoped) {
        const snapshot = getSnapshotForPubkey(pubkey);
        for (const callback of scoped) {
          callback(snapshot);
        }
      }
    }

    return result.identity;
  })();

  refreshInFlightByPubkey.set(pubkey, request);
  try {
    return await request;
  } finally {
    refreshInFlightByPubkey.delete(pubkey);
  }
};

const ensureCachedIdentityForPubkey = (pubkey: Pubkey): IdentityRecord | null => {
  const memoryEntry = memoryByPubkey.get(pubkey);
  if (memoryEntry) {
    return memoryEntry.notFound ? null : memoryEntry.identity;
  }

  const storageEntry = readIdentityFromStorage(pubkey);
  if (!storageEntry) return null;

  writeMemoryIdentity(pubkey, storageEntry.identity, storageEntry.notFound, "storage");
  return storageEntry.notFound ? null : storageEntry.identity;
};

const maybeRefreshActiveIdentity = async (reason: "boot" | "focus" | "signer-change") => {
  if (!activePubkey) return;
  const pubkey = activePubkey;
  const memoryEntry = memoryByPubkey.get(pubkey);
  const storageEntry = readIdentityFromStorage(pubkey);
  const shouldRefresh =
    reason === "boot" ||
    reason === "signer-change" ||
    !isMemoryFresh(memoryEntry) ||
    !isStorageFresh(storageEntry);

  if (!shouldRefresh) return;

  activeRefreshing = true;
  emitSnapshot(pubkey);
  emitCurrentIdentityEvent(getSnapshotForPubkey(pubkey));
  try {
    await refreshIdentity(pubkey);
  } finally {
    activeRefreshing = false;
    emitSnapshot(pubkey);
    emitCurrentIdentityEvent(getSnapshotForPubkey(pubkey));
  }
};

const reconcileWithSigner = async (
  reason: "boot" | "focus" | "event",
  neutralOnMissingSigner: boolean,
) => {
  const now = Date.now();
  if (reconciling) return;
  if (now - lastReconcileAt < MIN_RECONCILE_GAP_MS) return;
  reconciling = true;
  lastReconcileAt = now;

  try {
    const signerPubkey = await resolveSignerPubkey();

    if (!signerPubkey) {
      if (activePubkey && !activeAuthoritative) {
        if (signerWaitStartedAt === null) {
          signerWaitStartedAt = Date.now();
        }
        const elapsed = Date.now() - signerWaitStartedAt;
        if (elapsed >= SIGNER_GIVE_UP_MS) {
          setSignerStatus("timed_out");
        } else {
          setSignerStatus("checking");
        }
      } else {
        setSignerStatus("checking");
      }

      // Keep cached bootstrap state when signer is temporarily unavailable.
      // This avoids visual thrash from pubkey-seeded fallback -> unknown fallback.
      if (neutralOnMissingSigner && !activePubkey) {
        setActivePubkey(null, false);
      }
      return;
    }

    const switchedPubkey = signerPubkey !== activePubkey;
    writeLastPubkeyToStorage(signerPubkey);
    setActivePubkey(signerPubkey, true);
    setSignerStatus("confirmed");
    ensureCachedIdentityForPubkey(signerPubkey);
    emitSnapshot(signerPubkey);
    emitCurrentIdentityEvent(getSnapshotForPubkey(signerPubkey));

    await maybeRefreshActiveIdentity(
      reason === "boot" ? "boot" : switchedPubkey ? "signer-change" : "focus",
    );
  } finally {
    reconciling = false;
  }
};

const bootstrapFromCache = () => {
  const cachedPubkey = readLastPubkeyFromStorage();
  if (!cachedPubkey) {
    setActivePubkey(null, false);
    return;
  }

  setActivePubkey(cachedPubkey, false);
  ensureCachedIdentityForPubkey(cachedPubkey);
  emitSnapshot(cachedPubkey);
  emitCurrentIdentityEvent(getSnapshotForPubkey(cachedPubkey));
};

const attachLifecycleListeners = () => {
  window.addEventListener("focus", () => {
    void reconcileWithSigner("focus", false);
  });

  window.addEventListener("pageshow", () => {
    void reconcileWithSigner("focus", false);
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      void reconcileWithSigner("focus", false);
    }
  });

  window.setInterval(() => {
    void reconcileWithSigner("event", false);
  }, SIGNER_RECONCILE_INTERVAL_MS);
};

export const startIdentityStore = () => {
  if (typeof window === "undefined") return;
  if (started) return;
  started = true;
  bootstrapFromCache();
  attachLifecycleListeners();
  void reconcileWithSigner("boot", true);
};

export const getCurrentPubkey = async (
  options: GetCurrentPubkeyOptions = {},
): Promise<Pubkey | null> => {
  const allowCache = options.allowCache ?? true;
  if (!started) startIdentityStore();
  if (activePubkey) return activePubkey;
  if (allowCache) return readLastPubkeyFromStorage();
  const signerPubkey = await resolveSignerPubkey();
  if (signerPubkey) {
    writeLastPubkeyToStorage(signerPubkey);
    setActivePubkey(signerPubkey, true);
  }
  return signerPubkey;
};

export const getCurrentIdentity = async (
  options: GetCurrentIdentityOptions = {},
): Promise<IdentityRecord | null> => {
  const allowCache = options.allowCache ?? true;
  const pubkey = await getCurrentPubkey({ allowCache });
  if (!pubkey) return null;

  const memoryEntry = memoryByPubkey.get(pubkey);
  if (allowCache && isMemoryFresh(memoryEntry)) {
    return memoryEntry?.notFound ? null : (memoryEntry?.identity ?? null);
  }

  if (allowCache) {
    const cached = ensureCachedIdentityForPubkey(pubkey);
    if (cached) {
      void maybeRefreshActiveIdentity("focus");
      return cached;
    }
  }

  return refreshIdentity(pubkey);
};

export const clearIdentityCache = (rawPubkey?: string) => {
  if (typeof window === "undefined") return;
  if (rawPubkey) {
    const pubkey = parsePubkey(rawPubkey);
    if (!pubkey) return;
    memoryByPubkey.delete(pubkey);
    try {
      window.localStorage.removeItem(`${STORAGE_IDENTITY_PREFIX}${pubkey}`);
    } catch {
      // no-op
    }
    if (activePubkey === pubkey) {
      emitSnapshot(pubkey);
      emitCurrentIdentityEvent(getSnapshotForPubkey(pubkey));
    }
    return;
  }

  memoryByPubkey.clear();
  try {
    const keysToDelete: string[] = [];
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i);
      if (typeof key === "string" && key.startsWith(STORAGE_IDENTITY_PREFIX)) {
        keysToDelete.push(key);
      }
    }
    for (const key of keysToDelete) {
      window.localStorage.removeItem(key);
    }
  } catch {
    // no-op
  }
  emitSnapshot(activePubkey);
  emitCurrentIdentityEvent(getSnapshotForPubkey(activePubkey));
};

export const subscribeToIdentity = (
  rawPubkey: string,
  callback: IdentitySubscriber,
): (() => void) => {
  const pubkey = parsePubkey(rawPubkey);
  if (!pubkey) return () => {};

  const existing = subscribersByPubkey.get(pubkey) ?? new Set<IdentitySubscriber>();
  existing.add(callback);
  subscribersByPubkey.set(pubkey, existing);
  callback(getSnapshotForPubkey(pubkey));

  return () => {
    const set = subscribersByPubkey.get(pubkey);
    if (!set) return;
    set.delete(callback);
    if (set.size === 0) subscribersByPubkey.delete(pubkey);
  };
};

export const subscribeToCurrentIdentity = (
  callback: CurrentIdentitySubscriber,
): (() => void) => {
  currentSubscribers.add(callback);
  callback(getSnapshotForPubkey(activePubkey));

  return () => {
    currentSubscribers.delete(callback);
  };
};

export const signWithCurrentSigner = async <TSignedEvent = unknown>(
  unsignedEvent: { pubkey: Pubkey } & Record<string, unknown>,
  options: SignWithCurrentSignerOptions = {},
): Promise<TSignedEvent> => {
  const requirePubkeyMatch = options.requirePubkeyMatch ?? true;
  const signerPubkey = await getCurrentPubkey({ allowCache: false });
  if (!signerPubkey) {
    throw new Error("Signer pubkey is unavailable.");
  }

  const eventPubkey = parsePubkey(unsignedEvent.pubkey);
  if (!eventPubkey) {
    throw new Error("Unsigned event pubkey is invalid.");
  }
  if (requirePubkeyMatch && signerPubkey !== eventPubkey) {
    throw new Error("Signer pubkey does not match event pubkey.");
  }

  const signer = getSigner();
  if (!signer || typeof signer.signEvent !== "function") {
    throw new Error("Nostr signer is unavailable.");
  }

  const signedEvent = await signer.signEvent(unsignedEvent);
  return signedEvent as TSignedEvent;
};
