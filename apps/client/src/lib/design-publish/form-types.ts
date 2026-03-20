import type { Pubkey } from "~/lib/pubkey";

export type NostrTag = [string, string];

export type StepId =
  | "signer"
  | "file"
  | "name"
  | "format"
  | "description"
  | "additional-data"
  | "lightning-payments"
  | "design-images";

export type DesignPublishFormMode = "create" | "edit";

export type UnsignedNostrEvent = {
  kind: number;
  created_at: number;
  pubkey: Pubkey;
  tags: NostrTag[];
  content: string;
};

export type SignedNostrEvent = UnsignedNostrEvent & {
  id: string;
  sig: string;
};

export type BuildResult =
  | { ok: true; event: UnsignedNostrEvent; warnings: string[] }
  | { ok: false; errors: string[] };

export type Inputs = {
  d: string;
  previousVersionEventId: string;
  name: string;
  format: string;
  url: string;
  sha256: string;
  description: string;
  preview: string;
  category: string;
  material: string;
  printer: string;
  license: string;
  lnurl: string;
  mime: string;
};

export type FieldName = keyof Inputs;

export type DraftFieldName =
  | "name"
  | "format"
  | "url"
  | "sha256"
  | "description"
  | "preview"
  | "category"
  | "material"
  | "printer"
  | "license"
  | "mime";

export type DraftInputs = Pick<Inputs, DraftFieldName>;

export type FieldElement = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

export type IdentityMetadataDetail = {
  pubkey?: Pubkey | null;
  lnurl?: string | null;
};

export type SignerViewChangeDetail = {
  chipLabel?: string;
  signedDot?: "hidden" | "blinking" | "solid";
};

export type StepPanelNodes = {
  panel: HTMLElement;
  body: HTMLElement;
  toggle: HTMLButtonElement;
  summary: HTMLElement | null;
  backButton: HTMLButtonElement | null;
  nextButton: HTMLButtonElement | null;
  caretButton: HTMLButtonElement;
  caretIcon: HTMLElement;
};

export const STEP_ORDER: StepId[] = [
  "signer",
  "file",
  "name",
  "format",
  "description",
  "design-images",
  "lightning-payments",
  "additional-data",
];

export const INPUT_FIELD_NAMES: FieldName[] = [
  "d",
  "previousVersionEventId",
  "name",
  "format",
  "url",
  "sha256",
  "description",
  "preview",
  "category",
  "material",
  "printer",
  "license",
  "lnurl",
  "mime",
];

export const DRAFT_FIELD_NAMES: DraftFieldName[] = [
  "name",
  "format",
  "url",
  "sha256",
  "description",
  "preview",
  "category",
  "material",
  "printer",
  "license",
  "mime",
];
