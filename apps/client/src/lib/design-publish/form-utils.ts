import type { SignedNostrEvent } from "~/lib/design-publish/form-types";

export const FORMAT_RE = /^[a-z0-9][a-z0-9+.-]{0,31}$/;
export const SHA256_RE = /^[a-f0-9]{64}$/;
export const HEX_64_RE = /^[a-f0-9]{64}$/;
export const HEX_128_RE = /^[a-f0-9]{128}$/;
export const UUID_V4_RE =
  /^openprints:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

const CONTROL_OR_BIDI_RE = /[\u0000-\u001F\u007F-\u009F\u202A-\u202E\u2066-\u2069]/u;

const fallbackUuidV4 = (): string => {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};

export const generateDesignId = (): string => {
  const uuid = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : fallbackUuidV4();
  return `openprints:${uuid}`;
};

export const normalizeSingleLine = (value: string): string =>
  value.normalize("NFC").replace(/\s+/g, " ").trim();

export const normalizeTextArea = (value: string): string =>
  value.normalize("NFC").replace(/\r\n/g, "\n");

export const parseLineList = (value: string): string[] =>
  normalizeTextArea(value)
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

export const hasInvalidTextContent = (value: string): boolean => CONTROL_OR_BIDI_RE.test(value);

export const asHttpsUrl = (value: string): string | null => {
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
};

export const validateSignedEvent = (
  event: Partial<SignedNostrEvent> | null | undefined,
): event is SignedNostrEvent => {
  if (!event || typeof event !== "object") return false;
  if (typeof event.id !== "string" || !HEX_64_RE.test(event.id.toLowerCase())) return false;
  if (typeof event.sig !== "string" || !HEX_128_RE.test(event.sig.toLowerCase())) return false;
  if (event.kind !== 33301) return false;
  if (!Array.isArray(event.tags)) return false;
  if (typeof event.pubkey !== "string" || !HEX_64_RE.test(event.pubkey.toLowerCase())) return false;
  if (typeof event.created_at !== "number") return false;
  if (typeof event.content !== "string") return false;
  return true;
};
