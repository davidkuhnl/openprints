type NostrSignerLike = {
  getPublicKey?: () => Promise<string>;
  signEvent?: (event: unknown) => Promise<unknown>;
};

export type IdentityRecord = {
  id?: string | null;
  pubkey?: string | null;
  status?: string | null;
  display_name_resolved?: string | null;
  display_name?: string | null;
  name?: string | null;
  picture?: string | null;
  nip05?: string | null;
  lud06?: string | null;
  lud16?: string | null;
  lnurl?: string | null;
};

type IdentityCacheEntry = {
  pubkey: string;
  identity: IdentityRecord | null;
  notFound: boolean;
  cachedAt: number;
};

type CacheSource = "none" | "memory" | "storage" | "backend";

export type IdentitySnapshot = {
  pubkey: string | null;
  identity: IdentityRecord | null;
  authoritative: boolean;
  source: CacheSource;
  refreshing: boolean;
  updatedAt: number | null;
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
const MIN_RECONCILE_GAP_MS = 1_200;
const SIGNER_RECONCILE_INTERVAL_MS = 5_000;

const memoryByPubkey = new Map<string, MemoryIdentityEntry>();
const currentSubscribers = new Set<CurrentIdentitySubscriber>();
const subscribersByPubkey = new Map<string, Set<IdentitySubscriber>>();
const refreshInFlightByPubkey = new Map<string, Promise<IdentityRecord | null>>();

let started = false;
let reconciling = false;
let lastReconcileAt = 0;
let activePubkey: string | null = null;
let activeAuthoritative = false;
let activeRefreshing = false;

const normalizePubkey = (value: string | null | undefined): string =>
  typeof value === "string" ? value.trim().toLowerCase() : "";

const getSigner = (): NostrSignerLike | null => {
  if (typeof window === "undefined") return null;
  const w = window as Window & { nostr?: NostrSignerLike };
  return w.nostr ?? null;
};

const isMemoryFresh = (entry: MemoryIdentityEntry | undefined): boolean => {
  if (!entry) return false;
  return Date.now() - entry.fetchedAt < MEMORY_TTL_MS;
};

const isStorageFresh = (entry: IdentityCacheEntry | null): boolean => {
  if (!entry) return false;
  return Date.now() - entry.cachedAt < STORAGE_TTL_MS;
};

const getSnapshotForPubkey = (pubkey: string | null): IdentitySnapshot => {
  if (!pubkey) {
    return {
      pubkey: null,
      identity: null,
      authoritative: false,
      source: "none",
      refreshing: activeRefreshing,
      updatedAt: null,
    };
  }

  const memoryEntry = memoryByPubkey.get(pubkey);
  return {
    pubkey,
    identity: memoryEntry?.notFound ? null : (memoryEntry?.identity ?? null),
    authoritative: activeAuthoritative && activePubkey === pubkey,
    source: memoryEntry?.source ?? "none",
    refreshing: activeRefreshing,
    updatedAt: memoryEntry?.fetchedAt ?? null,
  };
};

const emitSnapshot = (pubkey: string | null) => {
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

const readLastPubkeyFromStorage = (): string | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_LAST_PUBKEY_KEY);
    const normalized = normalizePubkey(raw);
    return normalized.length > 0 ? normalized : null;
  } catch {
    return null;
  }
};

const writeLastPubkeyToStorage = (pubkey: string) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_LAST_PUBKEY_KEY, pubkey);
  } catch {
    // no-op
  }
};

const readIdentityFromStorage = (pubkey: string): IdentityCacheEntry | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(`${STORAGE_IDENTITY_PREFIX}${pubkey}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as IdentityCacheEntry;
    if (!parsed || normalizePubkey(parsed.pubkey) !== pubkey) return null;
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
  pubkey: string,
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
  pubkey: string,
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

const setActivePubkey = (pubkey: string | null, authoritative: boolean) => {
  activePubkey = pubkey;
  activeAuthoritative = authoritative && Boolean(pubkey);
  const snapshot = getSnapshotForPubkey(activePubkey);
  emitSnapshot(activePubkey);
  emitCurrentIdentityEvent(snapshot);
};

const resolveSignerPubkey = async (): Promise<string | null> => {
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
    const normalized = normalizePubkey(pubkey);
    if (!normalized) return null;
    return normalized;
  } catch {
    return null;
  }
};

const getApiBase = (): string => {
  const raw = import.meta.env.PUBLIC_OPENPRINTS_API_URL ?? "";
  return raw ? raw.replace(/\/$/, "") : "";
};

const fetchIdentityFromBackend = async (
  pubkey: string,
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

const maybeEmitIdentityMetadata = (pubkey: string, identity: IdentityRecord | null) => {
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
  const pubkey = normalizePubkey(rawPubkey);
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

const ensureCachedIdentityForPubkey = (pubkey: string): IdentityRecord | null => {
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
      if (neutralOnMissingSigner) {
        setActivePubkey(null, false);
      }
      return;
    }

    const switchedPubkey = signerPubkey !== activePubkey;
    writeLastPubkeyToStorage(signerPubkey);
    setActivePubkey(signerPubkey, true);
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
): Promise<string | null> => {
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
    const pubkey = normalizePubkey(rawPubkey);
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
  const pubkey = normalizePubkey(rawPubkey);
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
  unsignedEvent: { pubkey: string } & Record<string, unknown>,
  options: SignWithCurrentSignerOptions = {},
): Promise<TSignedEvent> => {
  const requirePubkeyMatch = options.requirePubkeyMatch ?? true;
  const signerPubkey = await getCurrentPubkey({ allowCache: false });
  if (!signerPubkey) {
    throw new Error("Signer pubkey is unavailable.");
  }

  const eventPubkey = normalizePubkey(unsignedEvent.pubkey);
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
