export interface ApiPublishRelayResult {
  relay: string;
  event_id: string;
  accepted: boolean;
  duplicate: boolean;
  message: string;
}

export interface ApiPublishError {
  message: string;
}

export interface ApiPublishResponse {
  ok: boolean;
  event_id: string | null;
  relay_results: ApiPublishRelayResult[];
  accepted_relay_count: number;
  duplicate_relay_count: number;
  rejected_relay_count: number;
  errors: ApiPublishError[];
}

export type ApiPublishResponseParseResult =
  | { ok: true; response: ApiPublishResponse }
  | { ok: false; reason: string };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const asStringOrNull = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

const asBoolean = (value: unknown): boolean | null =>
  typeof value === "boolean" ? value : null;

const asInteger = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) && Number.isInteger(value)
    ? value
    : null;

const parseRelayResult = (value: unknown): ApiPublishRelayResult | null => {
  if (!isRecord(value)) return null;
  const relay = asStringOrNull(value.relay);
  const eventId = asStringOrNull(value.event_id);
  const accepted = asBoolean(value.accepted);
  const duplicate = asBoolean(value.duplicate) ?? false;
  const message = asStringOrNull(value.message);

  if (relay == null || eventId == null || accepted == null || message == null) {
    return null;
  }

  return {
    relay,
    event_id: eventId,
    accepted,
    duplicate,
    message,
  };
};

const parsePublishError = (value: unknown): ApiPublishError | null => {
  if (!isRecord(value)) return null;
  const message = asStringOrNull(value.message);
  if (message == null) return null;
  return { message };
};

export const parseApiPublishResponse = (
  value: unknown,
): ApiPublishResponseParseResult => {
  if (!isRecord(value)) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt publish response: expected an object",
    };
  }

  const okValue = asBoolean(value.ok);
  if (okValue == null) {
    return {
      ok: false,
      reason: "malformed/invalid/corrupt publish response: missing ok flag",
    };
  }

  const relayResultsRaw = Array.isArray(value.relay_results) ? value.relay_results : [];
  const errorsRaw = Array.isArray(value.errors) ? value.errors : [];

  return {
    ok: true,
    response: {
      ok: okValue,
      event_id: asStringOrNull(value.event_id),
      relay_results: relayResultsRaw
        .map(parseRelayResult)
        .filter((item): item is ApiPublishRelayResult => item !== null),
      accepted_relay_count: asInteger(value.accepted_relay_count) ?? 0,
      duplicate_relay_count: asInteger(value.duplicate_relay_count) ?? 0,
      rejected_relay_count: asInteger(value.rejected_relay_count) ?? 0,
      errors: errorsRaw
        .map(parsePublishError)
        .filter((item): item is ApiPublishError => item !== null),
    },
  };
};
