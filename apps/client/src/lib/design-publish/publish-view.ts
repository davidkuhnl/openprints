export interface PublishSuccess {
  kind: "success";
  acceptedRelayCount: number;
  duplicateRelayCount: number;
  rejectedRelayCount: number;
}

export interface PublishFailure {
  kind: "failure";
  message: string;
}

export type PublishOutcome = PublishSuccess | PublishFailure;
