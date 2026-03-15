import {
  DRAFT_FIELD_NAMES,
  type DraftFieldName,
  type DraftInputs,
} from "~/lib/design-publish/form-types";

export const hasAnyDraftContent = (draft: DraftInputs): boolean =>
  DRAFT_FIELD_NAMES.some((field) => draft[field].trim().length > 0);

const parseDraft = (raw: string): DraftInputs | null => {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return null;

    const draft = {} as DraftInputs;
    for (const field of DRAFT_FIELD_NAMES) {
      const value = (parsed as Record<DraftFieldName, unknown>)[field];
      if (typeof value !== "string") return null;
      draft[field] = value;
    }
    return draft;
  } catch {
    return null;
  }
};

export const clearDraftFromSession = (storageKey: string) => {
  try {
    window.sessionStorage.removeItem(storageKey);
  } catch {
    // no-op
  }
};

export const saveDraftToSession = (storageKey: string, draft: DraftInputs) => {
  try {
    if (!hasAnyDraftContent(draft)) {
      window.sessionStorage.removeItem(storageKey);
      return;
    }
    window.sessionStorage.setItem(storageKey, JSON.stringify(draft));
  } catch {
    // no-op
  }
};

export const loadDraftFromSession = (storageKey: string): DraftInputs | null => {
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (!raw) return null;
    const draft = parseDraft(raw);
    if (!draft || !hasAnyDraftContent(draft)) {
      window.sessionStorage.removeItem(storageKey);
      return null;
    }
    return draft;
  } catch {
    return null;
  }
};
