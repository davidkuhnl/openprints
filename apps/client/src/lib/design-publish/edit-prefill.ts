import type { Inputs } from "~/lib/design-publish/form-types";
import type { ValidDesignDetail } from "~/lib/designs";

const getTagStringList = (tags: Record<string, unknown>, key: string): string[] => {
  const value = tags[key];
  if (Array.isArray(value)) {
    return value.filter(
      (item: unknown): item is string => typeof item === "string" && item.trim().length > 0,
    );
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return [value];
  }
  return [];
};

const getTagString = (tags: Record<string, unknown>, key: string): string => {
  return getTagStringList(tags, key)[0] ?? "";
};

const toMultiline = (values: string[]): string => values.join("\n");

export const buildEditInitialValues = (
  design: ValidDesignDetail,
  lockedDesignId: string,
): Inputs => {
  const tags = (design.tags_json ?? {}) as Record<string, unknown>;
  return {
    d: lockedDesignId,
    name: design.name ?? "",
    format: design.format ?? "",
    url: design.url ?? "",
    sha256: design.sha256 ?? "",
    description: design.content ?? "",
    preview: toMultiline(getTagStringList(tags, "preview")),
    category: toMultiline(getTagStringList(tags, "category")),
    material: toMultiline(getTagStringList(tags, "material")),
    printer: toMultiline(getTagStringList(tags, "printer")),
    license: getTagString(tags, "license"),
    lnurl: getTagString(tags, "lnurl"),
    mime: getTagString(tags, "m"),
  };
};
