import {
  parseApiDesignDetail,
  parseApiDesignListItems,
  parseApiDesignStats,
  parseApiDesignVersionList,
  type ApiDesignDetail,
  type ApiDesignListItem,
  type ApiDesignListItemParseResult,
  type ApiDesignVersionItem,
} from "~/lib/designs/api";
import type {
  DesignCardModel,
  DesignDetailModel,
  ValidDesignVersion,
  ValidDesignCard,
  ValidDesignDetail,
} from "~/lib/designs/view";

export const mapApiDesignListItemToCardModel = (item: ApiDesignListItem): ValidDesignCard => ({
  kind: "valid",
  id: item.id,
  pubkey: item.pubkey,
  name: item.name,
  content: item.content,
  creator_identity: item.creator_identity,
  latest_published_at: item.latest_published_at,
  version_count: item.version_count,
  format: item.format,
  tags_json: item.tags_json,
});

export const mapApiDesignParseResultToCardModel = (
  result: ApiDesignListItemParseResult,
): DesignCardModel =>
  result.ok
    ? mapApiDesignListItemToCardModel(result.item)
    : {
        kind: "invalid",
        reason: result.reason,
        raw_id: result.rawId,
        raw_payload: result.raw ?? null,
      };

export const mapUnknownDesignListToCardModels = (value: unknown): DesignCardModel[] =>
  parseApiDesignListItems(value).map(mapApiDesignParseResultToCardModel);

export const mapApiDesignDetailToDetailModel = (
  item: ApiDesignDetail,
): ValidDesignDetail => ({
  kind: "valid",
  id: item.id,
  pubkey: item.pubkey,
  creator_identity: item.creator_identity,
  design_id: item.design_id,
  latest_event_id: item.latest_event_id,
  latest_published_at: item.latest_published_at,
  first_published_at: item.first_published_at,
  first_seen_at: item.first_seen_at,
  updated_at: item.updated_at,
  version_count: item.version_count,
  name: item.name,
  format: item.format,
  sha256: item.sha256,
  url: item.url,
  content: item.content,
  tags_json: item.tags_json,
  endorsements: item.endorsements,
  endorsements_count: item.endorsements_count,
  zaps: item.zaps,
  total_zaps: item.total_zaps,
});

export const mapUnknownDesignDetailToDetailModel = (value: unknown): DesignDetailModel => {
  const result = parseApiDesignDetail(value);

  if (!result.ok) {
    return {
      kind: "invalid",
      reason: result.reason,
      raw_id: result.rawId,
      raw_payload: result.raw ?? null,
    };
  }

  return mapApiDesignDetailToDetailModel(result.item);
};

export const mapUnknownDesignStats = (
  value: unknown,
): { designs: number | null; versions: number | null } => {
  const parsed = parseApiDesignStats(value);
  if (!parsed.ok) {
    return { designs: null, versions: null };
  }
  return parsed.stats;
};

export const mapApiDesignVersionToVersionModel = (
  item: ApiDesignVersionItem,
): ValidDesignVersion => ({
  kind: "valid",
  event_id: item.event_id,
  pubkey: item.pubkey,
  design_id: item.design_id,
  previous_version_event_id: item.previous_version_event_id,
  event_kind: item.kind,
  created_at: item.created_at,
  received_at: item.received_at,
  name: item.name,
  format: item.format,
  sha256: item.sha256,
  url: item.url,
  content: item.content,
  tags_json: item.tags_json,
  raw_event_json: item.raw_event_json,
});

export const mapUnknownDesignVersions = (
  value: unknown,
): { items: ValidDesignVersion[]; total: number; limit: number; offset: number } => {
  const parsed = parseApiDesignVersionList(value);
  if (!parsed.ok) {
    return { items: [], total: 0, limit: 0, offset: 0 };
  }

  return {
    items: parsed.list.items.map(mapApiDesignVersionToVersionModel),
    total: parsed.list.total,
    limit: parsed.list.limit,
    offset: parsed.list.offset,
  };
};
