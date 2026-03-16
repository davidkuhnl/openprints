import type { ApiCreatorIdentity } from "~/lib/designs/api";

export type CreatorIdentityCard = ApiCreatorIdentity;
export type CreatorIdentityDetail = ApiCreatorIdentity;

export interface ValidDesignCard {
  kind: "valid";
  id: string;
  pubkey: string;
  name: string | null;
  content: string | null;
  creator_identity: CreatorIdentityCard | null;
  latest_published_at: number | null;
  format: string | null;
  tags_json: string | Record<string, unknown> | null;
}

export interface InvalidDesignCard {
  kind: "invalid";
  reason: string;
  raw_id: string | null;
  raw_payload: unknown | null;
}

export type DesignCardModel = ValidDesignCard | InvalidDesignCard;

export interface DesignDetailEndorsement {
  pubkey: string | null;
  content: string | null;
  created_at: number | null;
}

export interface DesignDetailZap {
  pubkey: string | null;
  amount: number | null;
}

export interface ValidDesignDetail {
  kind: "valid";
  id: string;
  pubkey: string;
  creator_identity: CreatorIdentityDetail | null;
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
  endorsements: DesignDetailEndorsement[];
  endorsements_count: number | null;
  zaps: DesignDetailZap[];
  total_zaps: number | null;
}

export interface InvalidDesignDetail {
  kind: "invalid";
  reason: string;
  raw_id: string | null;
  raw_payload: unknown | null;
}

export type DesignDetailModel = ValidDesignDetail | InvalidDesignDetail;
