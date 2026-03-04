export interface IdentityStatusInput {
  nip05?: string | null;
  lud06?: string | null;
  lud16?: string | null;
}

const hasNonEmptyValue = (value?: string | null): boolean =>
  typeof value === "string" && value.trim().length > 0;

export const getIdentityStatusFlags = (
  identity?: IdentityStatusInput | null,
) => {
  const hasNip05 = hasNonEmptyValue(identity?.nip05);
  const isZappable =
    hasNonEmptyValue(identity?.lud06) || hasNonEmptyValue(identity?.lud16);

  return {
    hasNip05,
    isZappable,
  };
};

