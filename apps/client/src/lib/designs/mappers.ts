import {
  parseApiDesignDetail,
  parseApiDesignListItems,
  parseApiDesignStats,
  type ApiDesignDetail,
  type ApiDesignListItem,
  type ApiDesignListItemParseResult,
} from "~/lib/designs/api";
import type {
  DesignCardModel,
  DesignDetailModel,
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
