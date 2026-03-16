import { parsePubkey, type Pubkey } from "~/lib/pubkey";

export interface ApiIdentity {
  id: string;
  pubkey: Pubkey;
  status: string | null;
  pubkey_first_seen_at: number | null;
  pubkey_last_seen_at: number | null;
  name: string | null;
  display_name: string | null;
  about: string | null;
  picture: string | null;
  banner: string | null;
  website: string | null;
  nip05: string | null;
  lud06: string | null;
  lud16: string | null;
  profile_raw_json: string | null;
  profile_fetched_at: number | null;
  fetch_last_attempt_at: number | null;
  retry_count: number | null;
  npub: string;
  display_name_resolved: string;
}

export type ApiIdentityParseResult =
  | { ok: true; identity: ApiIdentity }
  | { ok: false; reason: string };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const asStringOrNull = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const asTrimmedStringOrNull = (value: unknown): string | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
};

const asFiniteNumberOrNull = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const asIntegerOrNull = (value: unknown): number | null => {
  const n = asFiniteNumberOrNull(value);
  if (n == null) return null;
  return Number.isInteger(n) ? n : null;
};

export const parseApiIdentity = (value: unknown): ApiIdentityParseResult => {
  if (!isRecord(value)) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt identity payload: expected an object",
    };
  }

  const id = asTrimmedStringOrNull(value.id);
  const pubkey = typeof value.pubkey === "string" ? parsePubkey(value.pubkey) : null;
  const npub = asTrimmedStringOrNull(value.npub);
  const displayNameResolved = asTrimmedStringOrNull(value.display_name_resolved);

  if (!id || !pubkey || !npub || !displayNameResolved) {
    return {
      ok: false,
      reason:
        "malformed/invalid/corrupt identity payload: missing id/pubkey/npub/display_name_resolved",
    };
  }

  return {
    ok: true,
    identity: {
      id,
      pubkey,
      status: asStringOrNull(value.status),
      pubkey_first_seen_at: asFiniteNumberOrNull(value.pubkey_first_seen_at),
      pubkey_last_seen_at: asFiniteNumberOrNull(value.pubkey_last_seen_at),
      name: asStringOrNull(value.name),
      display_name: asStringOrNull(value.display_name),
      about: asStringOrNull(value.about),
      picture: asStringOrNull(value.picture),
      banner: asStringOrNull(value.banner),
      website: asStringOrNull(value.website),
      nip05: asStringOrNull(value.nip05),
      lud06: asStringOrNull(value.lud06),
      lud16: asStringOrNull(value.lud16),
      profile_raw_json: asStringOrNull(value.profile_raw_json),
      profile_fetched_at: asFiniteNumberOrNull(value.profile_fetched_at),
      fetch_last_attempt_at: asFiniteNumberOrNull(value.fetch_last_attempt_at),
      retry_count: asIntegerOrNull(value.retry_count),
      npub,
      display_name_resolved: displayNameResolved,
    },
  };
};
