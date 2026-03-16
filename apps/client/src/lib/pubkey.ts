export type Pubkey = string & { readonly __brand: "Pubkey" };

export const PUBKEY_HEX_RE = /^[a-f0-9]{64}$/;

const normalizePubkeyInput = (value: string): string => value.trim().toLowerCase();

export const parsePubkey = (value: string | null | undefined): Pubkey | null => {
  if (typeof value !== "string") return null;
  const normalized = normalizePubkeyInput(value);
  if (!PUBKEY_HEX_RE.test(normalized)) return null;
  return normalized as Pubkey;
};

export const isPubkey = (value: string | null | undefined): value is Pubkey =>
  parsePubkey(value) !== null;

export const pubkeysEqual = (
  left: string | Pubkey | null | undefined,
  right: string | Pubkey | null | undefined,
): boolean => {
  const normalizedLeft = parsePubkey(left);
  const normalizedRight = parsePubkey(right);
  return normalizedLeft !== null && normalizedLeft === normalizedRight;
};
