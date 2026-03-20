import type { ApiCreatorIdentity, DesignPubkey, DesignTags } from "~/lib/designs/api";
import type { Pubkey } from "~/lib/pubkey";

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
  version_count: number;
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
  pubkey: Pubkey | null;
  content: string | null;
  created_at: number | null;
}

export interface DesignDetailZap {
  pubkey: Pubkey | null;
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

export interface ValidDesignVersion {
  kind: "valid";
  event_id: string;
  pubkey: DesignPubkey;
  design_id: string;
  previous_version_event_id: string | null;
  event_kind: number;
  created_at: number;
  received_at: number;
  name: string | null;
  format: string | null;
  sha256: string | null;
  url: string | null;
  content: string | null;
  tags_json: DesignTags;
  raw_event_json: string;
}
