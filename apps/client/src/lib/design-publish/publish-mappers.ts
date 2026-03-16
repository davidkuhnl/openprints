import { parseApiPublishResponse } from "~/lib/design-publish/publish-api";
import type { PublishOutcome } from "~/lib/design-publish/publish-view";

export const mapPublishHttpResult = (
  httpOk: boolean,
  httpStatus: number,
  payload: unknown,
): PublishOutcome => {
  const parsed = parseApiPublishResponse(payload);
  if (!parsed.ok) {
    return {
      kind: "failure",
      message: `Publish failed (${httpStatus}).`,
    };
  }

  const { response } = parsed;
  const firstError = response.errors.find((error) => error.message.length > 0)?.message;
  if (!httpOk || !response.ok) {
    return {
      kind: "failure",
      message: firstError ?? `Publish failed (${httpStatus}).`,
    };
  }

  return {
    kind: "success",
    acceptedRelayCount: response.accepted_relay_count,
    duplicateRelayCount: response.duplicate_relay_count,
    rejectedRelayCount: response.rejected_relay_count,
  };
};
