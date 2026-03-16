import { parseApiIdentity } from "~/lib/identities/api";
import type { IdentityDetailModel } from "~/lib/identities/view";

export const mapUnknownIdentityToDetailModel = (
  value: unknown,
): { ok: true; identity: IdentityDetailModel } | { ok: false; reason: string } => {
  const parsed = parseApiIdentity(value);
  if (!parsed.ok) {
    return parsed;
  }
  return {
    ok: true,
    identity: parsed.identity,
  };
};
