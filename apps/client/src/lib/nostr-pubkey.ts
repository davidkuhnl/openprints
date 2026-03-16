import { nip19 } from "nostr-tools";
import { parsePubkey, type Pubkey } from "~/lib/pubkey";

export const parsePubkeyOrNpub = (value: string | null | undefined): Pubkey | null => {
  const pubkey = parsePubkey(value);
  if (pubkey) return pubkey;
  if (typeof value !== "string") return null;

  try {
    const decoded = nip19.decode(value.trim());
    if (decoded.type !== "npub" || typeof decoded.data !== "string") return null;
    return parsePubkey(decoded.data);
  } catch {
    return null;
  }
};
