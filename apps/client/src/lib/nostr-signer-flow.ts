type NostrSignerLike = {
  getPublicKey?: () => Promise<string>;
  signEvent?: (event: unknown) => Promise<unknown>;
};

export type SharedSignerState = {
  initialized: boolean;
  signerAvailable: boolean;
  pubkey: string | null;
  timedOut: boolean;
  pubkeyTimedOut: boolean;
  pubkeyPromise: Promise<string | null> | null;
  signerPollStarted: boolean;
};

type InitializeNostrSignerFlowOptions = {
  timeoutMs?: number;
  intervalMs?: number;
  pubkeyTimeoutMs?: number;
  useCachedPubkey?: boolean;
  onSignerAvailable?: () => void;
  onSignerMissingTimeout?: () => void;
  onPubkeyResolved?: (pubkey: string) => void;
  onPubkeyUnavailable?: (error?: unknown) => void;
};

const getNostrSigner = (): NostrSignerLike | null => {
  if (typeof window === "undefined") return null;
  const w = window as Window & { nostr?: NostrSignerLike };
  return w.nostr ?? null;
};

const isSignerAvailable = (): boolean => {
  const signer = getNostrSigner();
  return !!(
    signer &&
    typeof signer.getPublicKey === "function" &&
    typeof signer.signEvent === "function"
  );
};

const getPubkeyWithTimeout = (timeoutMs: number): Promise<string> => {
  const signer = getNostrSigner();
  if (!signer || typeof signer.getPublicKey !== "function") {
    return Promise.reject(new Error("Nostr signer is unavailable"));
  }

  return Promise.race([
    signer.getPublicKey(),
    new Promise<string>((_, reject) => {
      window.setTimeout(() => {
        reject(new Error("Timed out waiting for signer pubkey"));
      }, timeoutMs);
    }),
  ]);
};

const emit = (name: string, detail: Record<string, unknown> = {}) => {
  document.dispatchEvent(new CustomEvent(name, { detail }));
};

const getOrCreateSharedSignerState = (): SharedSignerState => {
  const w = window as Window & {
    __openprintsSignerState?: Partial<SharedSignerState>;
  };

  const current = w.__openprintsSignerState ?? {};
  const normalized: SharedSignerState = {
    initialized: true,
    signerAvailable: Boolean(current.signerAvailable),
    pubkey:
      typeof current.pubkey === "string" && current.pubkey.length > 0
        ? current.pubkey
        : null,
    timedOut: Boolean(current.timedOut),
    pubkeyTimedOut: Boolean(current.pubkeyTimedOut),
    pubkeyPromise:
      current.pubkeyPromise instanceof Promise ? current.pubkeyPromise : null,
    signerPollStarted: Boolean(current.signerPollStarted),
  };

  w.__openprintsSignerState = normalized;
  return normalized;
};

const resolvePubkeyOnce = async (
  state: SharedSignerState,
  pubkeyTimeoutMs: number,
  options: InitializeNostrSignerFlowOptions,
): Promise<string | null> => {
  if (state.pubkeyPromise) return state.pubkeyPromise;

  state.pubkeyPromise = getPubkeyWithTimeout(pubkeyTimeoutMs)
    .then((pubkey) => {
      if (typeof pubkey === "string" && pubkey.length > 0) {
        state.pubkey = pubkey;
        emit("nostr-signer-ready", { pubkey });
        options.onPubkeyResolved?.(pubkey);
        return pubkey;
      }
      emit("nostr-signer-ready", { pubkey: null });
      options.onPubkeyUnavailable?.();
      return null;
    })
    .catch((error) => {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes("Timed out waiting for signer pubkey")) {
        state.pubkeyTimedOut = true;
        emit("nostr-signer-pubkey-timeout", { error });
      }
      emit("nostr-signer-ready", { pubkey: null, error });
      options.onPubkeyUnavailable?.(error);
      return null;
    });

  return state.pubkeyPromise;
};

export const initializeNostrSignerFlow = (
  options: InitializeNostrSignerFlowOptions = {},
) => {
  if (typeof window === "undefined") return null;

  const timeoutMs = options.timeoutMs ?? 60000;
  const intervalMs = options.intervalMs ?? 750;
  const pubkeyTimeoutMs = options.pubkeyTimeoutMs ?? 10000;

  const state = getOrCreateSharedSignerState();

  const markSignerAvailable = () => {
    options.onSignerAvailable?.();
    if (!state.signerAvailable) {
      state.signerAvailable = true;
      emit("nostr-signer-available");
    }
    void resolvePubkeyOnce(state, pubkeyTimeoutMs, options);
  };

  const cachedPubkey =
    typeof state.pubkey === "string" && state.pubkey.length > 0
      ? state.pubkey
      : null;
  if (options.useCachedPubkey && cachedPubkey) {
    options.onSignerAvailable?.();
    options.onPubkeyResolved?.(cachedPubkey);
    return state;
  }

  const waitForSigner = () => {
    if (state.signerPollStarted) return;
    state.signerPollStarted = true;

    const started = Date.now();
    const tick = () => {
      if (isSignerAvailable()) {
        markSignerAvailable();
        return;
      }
      if (Date.now() - started > timeoutMs) {
        state.timedOut = true;
        emit("nostr-signer-timeout");
        options.onSignerMissingTimeout?.();
        return;
      }
      window.setTimeout(tick, intervalMs);
    };
    tick();
  };

  if (isSignerAvailable()) {
    markSignerAvailable();
  } else {
    waitForSigner();
  }

  return state;
};
