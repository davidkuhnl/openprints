import type { ApiCreatorIdentity, DesignPubkey, DesignTags } from "~/lib/designs/api";

export type CreatorIdentityCard = ApiCreatorIdentity;
export type CreatorIdentityDetail = ApiCreatorIdentity;

export interface ValidDesignCard {
  kind: "valid";
  id: string;
  pubkey: DesignPubkey;
  name: string;
  content: string | null;
  creator_identity: CreatorIdentityCard;
  latest_published_at: number;
  format: string | null;
  tags_json: DesignTags;
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
  pubkey: DesignPubkey;
  creator_identity: CreatorIdentityDetail;
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
