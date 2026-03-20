import type { BuildResult, Inputs, NostrTag } from "~/lib/design-publish/form-types";
import {
  EVENT_ID_RE,
  FORMAT_RE,
  SHA256_RE,
  UUID_V4_RE,
  asHttpsUrl,
  hasInvalidTextContent,
  normalizeSingleLine,
  normalizeTextArea,
  parseLineList,
} from "~/lib/design-publish/form-utils";
import { parsePubkey } from "~/lib/pubkey";

const OPENPRINTS_SCHEMA_VERSION = "1.1";

export const buildUnsignedEvent = (inputs: Inputs, pubkey: string): BuildResult => {
  const errors: string[] = [];
  const warnings: string[] = [];

  const d = normalizeSingleLine(inputs.d).toLowerCase();
  if (!UUID_V4_RE.test(d)) {
    errors.push("Design id is missing or invalid. Reload to generate a valid id.");
  }

  const previousVersionEventId = normalizeSingleLine(inputs.previousVersionEventId).toLowerCase();
  if (previousVersionEventId && !EVENT_ID_RE.test(previousVersionEventId)) {
    errors.push("Previous version event id must be exactly 64 lowercase hex characters.");
  }

  const name = normalizeSingleLine(inputs.name);
  if (!name) errors.push("Name is required.");
  else if (name.length > 120) errors.push("Name must be at most 120 characters.");
  else if (hasInvalidTextContent(name)) {
    errors.push("Name contains unsupported control or bidi characters.");
  }

  const format = normalizeSingleLine(inputs.format).toLowerCase();
  if (!format) errors.push("Format is required.");
  else if (!FORMAT_RE.test(format)) {
    errors.push("Format must be lowercase and use only [a-z0-9+.-].");
  }

  const urlValue = normalizeSingleLine(inputs.url);
  const normalizedUrl = asHttpsUrl(urlValue);
  if (!normalizedUrl) errors.push("File URL must be a valid https URL.");

  const sha256Raw = normalizeSingleLine(inputs.sha256).toLowerCase();
  const sha256 = sha256Raw || "";
  if (sha256 && !SHA256_RE.test(sha256)) {
    errors.push("SHA-256 must be exactly 64 lowercase hex characters.");
  } else if (!sha256) {
    warnings.push("No sha256 provided (allowed in V1).");
  }

  const content = normalizeTextArea(inputs.description).trim();
  if (hasInvalidTextContent(content)) {
    errors.push("Description contains unsupported control or bidi characters.");
  }

  const previewValues = parseLineList(inputs.preview);
  const previewUrls: string[] = [];
  for (const preview of previewValues) {
    const url = asHttpsUrl(preview);
    if (!url) errors.push(`Preview URL is invalid: ${preview}`);
    else previewUrls.push(url);
  }

  const categoryValues = parseLineList(inputs.category).map((entry) =>
    normalizeSingleLine(entry),
  );
  const materialValues = parseLineList(inputs.material).map((entry) =>
    normalizeSingleLine(entry),
  );
  const printerValues = parseLineList(inputs.printer).map((entry) =>
    normalizeSingleLine(entry),
  );
  const license = normalizeSingleLine(inputs.license);
  const lnurl = normalizeSingleLine(inputs.lnurl);
  const mime = normalizeSingleLine(inputs.mime).toLowerCase();

  const textTagValues = [
    ...categoryValues,
    ...materialValues,
    ...printerValues,
    license,
    lnurl,
    mime,
  ].filter((v) => v.length > 0);

  for (const value of textTagValues) {
    if (hasInvalidTextContent(value)) {
      errors.push(`Tag value contains unsupported control or bidi characters: ${value}`);
    }
  }

  const normalizedPubkey = parsePubkey(pubkey);
  if (!normalizedPubkey) errors.push("Signer pubkey is not available yet.");

  if (errors.length > 0) return { ok: false, errors };

  const tags: NostrTag[] = [
    ["d", d],
    ["openprints_schema", OPENPRINTS_SCHEMA_VERSION],
    ["name", name],
    ["format", format],
    ["url", normalizedUrl as string],
  ];
  if (previousVersionEventId) {
    tags.push(["previous", previousVersionEventId]);
  }

  if (sha256) tags.push(["sha256", sha256]);
  for (const previewUrl of previewUrls) tags.push(["preview", previewUrl]);
  for (const category of categoryValues) tags.push(["category", category]);
  for (const material of materialValues) tags.push(["material", material]);
  for (const printer of printerValues) tags.push(["printer", printer]);
  if (license) tags.push(["license", license]);
  if (lnurl) tags.push(["lnurl", lnurl]);
  if (mime) tags.push(["m", mime]);

  return {
    ok: true,
    event: {
      kind: 33301,
      created_at: Math.floor(Date.now() / 1000),
      pubkey: normalizedPubkey,
      tags,
      content,
    },
    warnings,
  };
};
