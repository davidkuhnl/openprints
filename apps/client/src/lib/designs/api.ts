export interface ApiCreatorIdentity {
  id: string | null;
  status: string | null;
  pubkey: string;
  display_name_resolved: string;
  npub: string;
  picture: string | null;
  nip05: string | null;
  lud06: string | null;
  lud16: string | null;
}

export interface ApiDesignListItem {
  id: string;
  pubkey: string;
  name: string | null;
  content: string | null;
  creator_identity: ApiCreatorIdentity | null;
  latest_published_at: number | null;
  format: string | null;
  tags_json: string | Record<string, unknown> | null;
}

export interface ApiDesignDetail {
  id: string;
  pubkey: string;
  creator_identity: ApiCreatorIdentity | null;
  design_id: string | null;
  latest_event_id: string | null;
  latest_published_at: number | null;
  first_published_at: number | null;
  first_seen_at: number | null;
  updated_at: number | null;
  version_count: number | null;
  name: string | null;
  format: string | null;
  sha256: string | null;
  url: string | null;
  content: string | null;
  tags_json: string | Record<string, unknown> | null;
  endorsements: ApiDesignEndorsement[];
  endorsements_count: number | null;
  zaps: ApiDesignZap[];
  total_zaps: number | null;
}

export interface ApiDesignEndorsement {
  pubkey: string | null;
  content: string | null;
  created_at: number | null;
}

export interface ApiDesignZap {
  pubkey: string | null;
  amount: number | null;
}

export interface ApiDesignStats {
  designs: number;
  versions: number;
}

export type ApiDesignListItemParseResult =
  | { ok: true; item: ApiDesignListItem }
  | { ok: false; reason: string; rawId: string | null };

export type ApiDesignDetailParseResult =
  | { ok: true; item: ApiDesignDetail }
  | { ok: false; reason: string; rawId: string | null };

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

const asFiniteNumberOrNull = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const asIntegerOrNull = (value: unknown): number | null => {
  const numberValue = asFiniteNumberOrNull(value);
  if (numberValue == null) return null;
  return Number.isInteger(numberValue) ? numberValue : null;
};

const parseEndorsement = (value: unknown): ApiDesignEndorsement | null => {
  if (!isRecord(value)) return null;
  return {
    pubkey: asStringOrNull(value.pubkey),
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
  return {
    pubkey: asStringOrNull(value.pubkey),
    amount,
  };
};

const parseApiCreatorIdentity = (value: unknown): ApiCreatorIdentity | null => {
  if (!isRecord(value)) return null;

  const pubkey = asTrimmedStringOrNull(value.pubkey);
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
    nip05: asStringOrNull(value.nip05),
    lud06: asStringOrNull(value.lud06),
    lud16: asStringOrNull(value.lud16),
  };
};

export const parseApiDesignListItem = (value: unknown): ApiDesignListItemParseResult => {
  if (!isRecord(value)) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design payload: expected an object",
      rawId: null,
    };
  }

  const id = asTrimmedStringOrNull(value.id);
  const pubkey = asTrimmedStringOrNull(value.pubkey);

  if (!id) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design payload: missing design id",
      rawId: null,
    };
  }

  if (!pubkey) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt design payload: missing design pubkey",
      rawId: id,
    };
  }

  const tagsJson =
    typeof value.tags_json === "string" || isRecord(value.tags_json)
      ? value.tags_json
      : null;

  return {
    ok: true,
    item: {
      id,
      pubkey,
      name: asStringOrNull(value.name),
      content: asStringOrNull(value.content),
      creator_identity: parseApiCreatorIdentity(value.creator_identity),
      latest_published_at: asFiniteNumberOrNull(value.latest_published_at),
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
    return listResult;
  }

  const raw = isRecord(value) ? value : {};
  const endorsementsRaw = Array.isArray(raw.endorsements) ? raw.endorsements : [];
  const zapsRaw = Array.isArray(raw.zaps) ? raw.zaps : [];

  return {
    ok: true,
    item: {
      ...listResult.item,
      design_id: asStringOrNull(raw.design_id),
      latest_event_id: asStringOrNull(raw.latest_event_id),
      first_published_at: asFiniteNumberOrNull(raw.first_published_at),
      first_seen_at: asFiniteNumberOrNull(raw.first_seen_at),
      updated_at: asFiniteNumberOrNull(raw.updated_at),
      version_count: asIntegerOrNull(raw.version_count),
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
