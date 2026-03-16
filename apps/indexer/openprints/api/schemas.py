"""Pydantic response schemas for API routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    message: str


class IdentityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    pubkey: str
    status: Literal["pending", "fetched", "failed"] | None = None
    pubkey_first_seen_at: int | None = None
    pubkey_last_seen_at: int | None = None
    name: str | None = None
    display_name: str | None = None
    about: str | None = None
    picture: str | None = None
    banner: str | None = None
    website: str | None = None
    nip05: str | None = None
    lud06: str | None = None
    lud16: str | None = None
    profile_raw_json: str | None = None
    profile_fetched_at: int | None = None
    fetch_last_attempt_at: int | None = None
    retry_count: int | None = None
    npub: str
    display_name_resolved: str


class DesignItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    pubkey: str
    creator_identity: IdentityPayload
    design_id: str
    latest_event_id: str
    latest_published_at: int
    first_published_at: int
    first_seen_at: int
    updated_at: int
    version_count: int
    name: str | None = None
    format: str | None = None
    sha256: str | None = None
    url: str | None = None
    content: str | None = None
    tags_json: str | dict[str, object]


class DesignListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DesignItemPayload]
    total: int
    limit: int
    offset: int


class DesignStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    designs: int
    versions: int


class PublishRelayResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relay: str
    event_id: str
    accepted: bool
    duplicate: bool = False
    message: str


class PublishDesignResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    event_id: str | None = None
    relay_results: list[PublishRelayResult] = []
    accepted_relay_count: int = 0
    duplicate_relay_count: int = 0
    rejected_relay_count: int = 0
    errors: list[ApiError] = []


class SignedDesignEvent(BaseModel):
    """Request body schema for POST /designs/publish (matches Nostr signed event)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    pubkey: str
    created_at: int
    kind: int
    tags: list[list[str]]
    content: str
    sig: str
