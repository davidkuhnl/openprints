import { parsePubkey, type Pubkey } from "~/lib/pubkey";

export interface ApiCreatorIdentity {
  id: string | null;
  status: string | null;
  pubkey: DesignPubkey;
  display_name_resolved: string;
  npub: string;
  picture: string | null;
  shape: string | null;
  nip05: string | null;
  lud06: string | null;
  lud16: string | null;
}

export type DesignPubkey = Pubkey;
export type DesignTags = Record<string, unknown> & { readonly __brand: "DesignTags" };

export interface ApiDesignListItem {
  id: string;
  pubkey: DesignPubkey;
  name: string;
  content: string | null;
  creator_identity: ApiCreatorIdentity;
  latest_published_at: number;
  format: string | null;
  tags_json: DesignTags;
}

export interface ApiDesignDetail {
  id: string;
  pubkey: DesignPubkey;
  creator_identity: ApiCreatorIdentity;
  design_id: string | null;
  latest_event_id: string | null;
  latest_published_at: number;
  first_published_at: number;
  first_seen_at: number;
  updated_at: number;
  version_count: number;
  name: string;
  format: string | null;
  sha256: string | null;
  url: string | null;
  content: string | null;
  tags_json: DesignTags;
  endorsements: ApiDesignEndorsement[];
  endorsements_count: number | null;
  zaps: ApiDesignZap[];
  total_zaps: number | null;
}

export interface ApiDesignEndorsement {
  pubkey: Pubkey | null;
  content: string | null;
  created_at: number | null;
}

export interface ApiDesignZap {
  pubkey: Pubkey | null;
  amount: number | null;
}

export interface ApiDesignStats {
  designs: number;
  versions: number;
}

export type ApiDesignListItemParseResult =
  | { ok: true; item: ApiDesignListItem }
  | { ok: false; reason: string; rawId: string | null; raw: unknown | null };

export type ApiDesignDetailParseResult =
  | { ok: true; item: ApiDesignDetail }
  | { ok: false; reason: string; rawId: string | null; raw: unknown | null };

export type ApiDesignStatsParseResult =
  | { ok: true; stats: ApiDesignStats }
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

const asDesignPubkeyOrNull = (value: unknown): DesignPubkey | null => {
  if (typeof value !== "string") return null;
  return parsePubkey(value);
};

const asFiniteNumberOrNull = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const asIntegerOrNull = (value: unknown): number | null => {
  const numberValue = asFiniteNumberOrNull(value);
  if (numberValue == null) return null;
  return Number.isInteger(numberValue) ? numberValue : null;
};

const parseEndorsement = (value: unknown): ApiDesignEndorsement | null => {
  if (!isRecord(value)) return null;
  const pubkey = typeof value.pubkey === "string" ? parsePubkey(value.pubkey) : null;
  return {
    pubkey,
    content: asStringOrNull(value.content),
    created_at: asFiniteNumberOrNull(value.created_at),
  };
};

const parseZap = (value: unknown): ApiDesignZap | null => {
  if (!isRecord(value)) return null;
  const amount =
    asFiniteNumberOrNull(value.amount) ??
    asFiniteNumberOrNull(value.value) ??
    asFiniteNumberOrNull(value.sats);
  const pubkey = typeof value.pubkey === "string" ? parsePubkey(value.pubkey) : null;
  return {
    pubkey,
    amount,
  };
};

const parseApiCreatorIdentity = (value: unknown): ApiCreatorIdentity | null => {
  if (!isRecord(value)) return null;

  const pubkey = asDesignPubkeyOrNull(value.pubkey);
  const displayNameResolved = asTrimmedStringOrNull(value.display_name_resolved);
  const npub = asTrimmedStringOrNull(value.npub);

  if (!pubkey || !displayNameResolved || !npub) {
    return null;
  }

  return {
    id: asStringOrNull(value.id),
    status: asStringOrNull(value.status),
    pubkey,
    display_name_resolved: displayNameResolved,
    npub,
    picture: asStringOrNull(value.picture),
    shape: asStringOrNull(value.shape),
    nip05: asStringOrNull(value.nip05),
    lud06: asStringOrNull(value.lud06),
    lud16: asStringOrNull(value.lud16),
  };
};

const parseDesignTagsOrNull = (value: unknown): DesignTags | null => {
  let parsed: unknown = value;

  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value);
    } catch {
      return null;
    }
  }

  if (!isRecord(parsed)) return null;
  if (Object.keys(parsed).some((key) => key.trim().length === 0)) return null;
  return parsed as DesignTags;
};

export const parseApiDesignListItem = (value: unknown): ApiDesignListItemParseResult => {
  if (!isRecord(value)) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design payload: expected an object",
      rawId: null,
      raw: value,
    };
  }

  const id = asTrimmedStringOrNull(value.id);
  const pubkey = asDesignPubkeyOrNull(value.pubkey);
  const name = asTrimmedStringOrNull(value.name);
  const latestPublishedAt = asFiniteNumberOrNull(value.latest_published_at);
  const tagsJson = parseDesignTagsOrNull(value.tags_json);
  const creatorIdentity = parseApiCreatorIdentity(value.creator_identity);

  if (!id) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design payload: missing design id",
      rawId: null,
      raw: value,
    };
  }

  if (!pubkey) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design payload: missing or invalid design pubkey",
      rawId: id,
      raw: value,
    };
  }

  if (!name) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design payload: missing design name",
      rawId: id,
      raw: value,
    };
  }

  if (!tagsJson) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design payload: invalid design tags_json object",
      rawId: id,
      raw: value,
    };
  }

  if (!creatorIdentity) {
    return {
      ok: false,
      reason:
        "malformed/invalid/corrupt design payload: missing or invalid creator_identity",
      rawId: id,
      raw: value,
    };
  }

  if (latestPublishedAt == null) {
    return {
      ok: false,
      reason:
        "malformed/invalid/corrupt design payload: missing or invalid latest_published_at timestamp",
      rawId: id,
      raw: value,
    };
  }

  return {
    ok: true,
    item: {
      id,
      pubkey,
      name,
      content: asStringOrNull(value.content),
      creator_identity: creatorIdentity,
      latest_published_at: latestPublishedAt,
      format: asStringOrNull(value.format),
      tags_json: tagsJson,
    },
  };
};

export const parseApiDesignListItems = (value: unknown): ApiDesignListItemParseResult[] => {
  if (!Array.isArray(value)) return [];
  return value.map(parseApiDesignListItem);
};

export const parseApiDesignDetail = (value: unknown): ApiDesignDetailParseResult => {
  const listResult = parseApiDesignListItem(value);
  if (!listResult.ok) {
    return {
      ok: false,
      reason: listResult.reason,
      rawId: listResult.rawId,
      raw: listResult.raw ?? value,
    };
  }

  const raw = isRecord(value) ? value : {};
  const endorsementsRaw = Array.isArray(raw.endorsements) ? raw.endorsements : [];
  const zapsRaw = Array.isArray(raw.zaps) ? raw.zaps : [];

  const firstPublishedAt = asFiniteNumberOrNull(raw.first_published_at);
  const firstSeenAt = asFiniteNumberOrNull(raw.first_seen_at);
  const updatedAt = asFiniteNumberOrNull(raw.updated_at);
  const versionCount = asIntegerOrNull(raw.version_count);

  if (
    firstPublishedAt == null ||
    firstSeenAt == null ||
    updatedAt == null ||
    versionCount == null
  ) {
    return {
      ok: false,
      reason:
        "malformed/invalid/corrupt design detail payload: missing or invalid required timestamps or version_count",
      rawId: listResult.item.id,
      raw: value,
    };
  }

  return {
    ok: true,
    item: {
      ...listResult.item,
      design_id: asStringOrNull(raw.design_id),
      latest_event_id: asStringOrNull(raw.latest_event_id),
      first_published_at: firstPublishedAt,
      first_seen_at: firstSeenAt,
      updated_at: updatedAt,
      version_count: versionCount,
      sha256: asStringOrNull(raw.sha256),
      url: asStringOrNull(raw.url),
      endorsements: endorsementsRaw
        .map(parseEndorsement)
        .filter((item): item is ApiDesignEndorsement => item !== null),
      endorsements_count: asIntegerOrNull(raw.endorsements_count),
      zaps: zapsRaw.map(parseZap).filter((item): item is ApiDesignZap => item !== null),
      total_zaps:
        asFiniteNumberOrNull(raw.total_zaps) ?? asFiniteNumberOrNull(raw.totalZaps),
    },
  };
};

export const parseApiDesignStats = (value: unknown): ApiDesignStatsParseResult => {
  if (!isRecord(value)) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design stats payload: expected an object",
    };
  }

  const designs = asIntegerOrNull(value.designs);
  const versions = asIntegerOrNull(value.versions);
  if (designs == null || versions == null) {
    return {
      ok: false,
      reason:
        "malformed/invalid/corrupt design stats payload: missing integer designs/versions",
    };
  }

  return {
    ok: true,
    stats: {
      designs,
      versions,
    },
  };
};
