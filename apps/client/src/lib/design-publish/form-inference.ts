import { normalizeSingleLine } from "~/lib/design-publish/form-utils";

const MIME_BY_FORMAT: Record<string, string> = {
  stl: "model/stl",
  "3mf": "model/3mf",
  obj: "model/obj",
  gcode: "text/x.gcode",
};

const EXTENSION_TO_FORMAT: Record<string, string> = {
  ".stl": "stl",
  ".3mf": "3mf",
  ".step": "step",
  ".stp": "step",
  ".obj": "obj",
  ".gcode": "gcode",
};

export const getSuggestedMimeForFormat = (format: string): string | undefined => {
  const normalized = normalizeSingleLine(format).toLowerCase();
  if (!normalized) return undefined;
  return MIME_BY_FORMAT[normalized];
};

export const getFormatFromUrl = (raw: string): string | undefined => {
  const value = raw.trim();
  if (!value) return undefined;
  let path = value.toLowerCase();
  try {
    const url = new URL(value);
    path = url.pathname.toLowerCase();
  } catch {
    // fall back to raw string
  }
  const match = Object.keys(EXTENSION_TO_FORMAT).find((ext) => path.endsWith(ext));
  return match ? EXTENSION_TO_FORMAT[match] : undefined;
};

export const getDesignNameFromUrl = (raw: string): string | undefined => {
  const value = raw.trim();
  if (!value) return undefined;
  let path = value;
  try {
    const url = new URL(value);
    path = url.pathname;
  } catch {
    // fall back to raw string
  }

  const segments = path.split("/").filter((segment) => segment.length > 0);
  if (segments.length === 0) return undefined;
  const file = segments[segments.length - 1];

  const withoutQuery = file.split("?")[0].split("#")[0];
  const dotIndex = withoutQuery.lastIndexOf(".");
  const base = dotIndex > 0 ? withoutQuery.slice(0, dotIndex) : withoutQuery;
  const cleaned = base.replace(/[-_]+/g, " ").trim();
  if (!cleaned) return undefined;

  return cleaned
    .toLowerCase()
    .split(" ")
    .filter((part) => part.length > 0)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
};
