import argparse

from openprints.common.signers.factory import SUPPORTED_SIGNERS

from .commands.build import run_build_design, run_build_identity
from .commands.db import run_db_stats, run_db_wipe
from .commands.hash import run_hash
from .commands.index import run_index
from .commands.keygen import run_keygen
from .commands.publish import run_publish
from .commands.serve import run_serve
from .commands.sign import run_sign
from .commands.subscribe import run_subscribe


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openprints-cli")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="Build a draft event payload")
    build_subparsers = build_parser.add_subparsers(dest="build_command", required=True)

    build_design_parser = build_subparsers.add_parser(
        "design",
        help="Build a draft design event payload (kind 33301)",
    )
    build_design_parser.add_argument("--name", required=True, help="Human-readable design name.")
    build_design_parser.add_argument(
        "--design-id",
        default=None,
        help="Optional design id (uuid or openprints:uuid). If omitted, a uuid-v4 is generated.",
    )
    build_design_parser.add_argument(
        "--format", required=True, help="Design file format (for example stl)."
    )
    build_design_parser.add_argument(
        "--url", required=True, help="Public URL where the design file is hosted."
    )
    build_design_parser.add_argument(
        "--content",
        default="",
        help="Optional Markdown description to include in event.content.",
    )
    build_hash_input = build_design_parser.add_mutually_exclusive_group(required=True)
    build_hash_input.add_argument(
        "--file",
        default=None,
        help="Path to local file to hash as event.tags[sha256].",
    )
    build_hash_input.add_argument(
        "--sha256",
        default=None,
        help="Precomputed SHA-256 digest for event.tags[sha256].",
    )
    build_design_parser.add_argument(
        "--output",
        default="-",
        help="Output path for payload JSON, or '-' for stdout (default).",
    )
    build_design_parser.set_defaults(func=run_build_design)

    build_identity_parser = build_subparsers.add_parser(
        "identity",
        help="Build a draft identity metadata payload (kind 0)",
    )
    build_identity_parser.add_argument(
        "--profile-file",
        required=True,
        help="Path to identity profile JSON object for event.content.",
    )
    build_identity_parser.add_argument(
        "--output",
        default="-",
        help="Output path for payload JSON, or '-' for stdout (default).",
    )
    build_identity_parser.set_defaults(func=run_build_identity)

    publish_parser = subparsers.add_parser("publish", help="Publish a signed event to relay(s)")
    publish_subparsers = publish_parser.add_subparsers(dest="publish_command", required=True)
    publish_design_parser = publish_subparsers.add_parser(
        "design",
        help="Publish a signed design payload",
    )
    publish_design_parser.add_argument(
        "--input",
        default="-",
        help="Input path for payload JSON, or '-' for stdin (default).",
    )
    publish_design_parser.add_argument(
        "--relay",
        default=None,
        help="Relay websocket URL (ws:// or wss://). Falls back to env if omitted.",
    )
    publish_design_parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Relay connect/ack timeout in seconds (default: 8.0).",
    )
    publish_design_parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Number of retry attempts for transport/timeouts (default: 0).",
    )
    publish_design_parser.add_argument(
        "--retry-backoff-ms",
        type=int,
        default=400,
        help="Delay between retry attempts in milliseconds (default: 400).",
    )
    publish_design_parser.set_defaults(func=run_publish, publish_event_type="design")

    publish_identity_parser = publish_subparsers.add_parser(
        "identity",
        help="Publish a signed identity payload",
    )
    publish_identity_parser.add_argument(
        "--input",
        default="-",
        help="Input path for payload JSON, or '-' for stdin (default).",
    )
    publish_identity_parser.add_argument(
        "--relay",
        default=None,
        help="Relay websocket URL (ws:// or wss://). Falls back to env if omitted.",
    )
    publish_identity_parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Relay connect/ack timeout in seconds (default: 8.0).",
    )
    publish_identity_parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Number of retry attempts for transport/timeouts (default: 0).",
    )
    publish_identity_parser.add_argument(
        "--retry-backoff-ms",
        type=int,
        default=400,
        help="Delay between retry attempts in milliseconds (default: 400).",
    )
    publish_identity_parser.set_defaults(func=run_publish, publish_event_type="identity")

    sign_parser = subparsers.add_parser("sign", help="Sign a draft payload")
    sign_parser.add_argument(
        "--input",
        default="-",
        help="Input path for payload JSON, or '-' for stdin (default).",
    )
    sign_parser.add_argument(
        "--signer",
        default="dev-nsec",
        choices=SUPPORTED_SIGNERS,
        help="Signer backend to use (default: dev-nsec).",
    )
    sign_parser.add_argument(
        "--nsec-env",
        default="OPENPRINTS_DEV_NSEC",
        help="Environment variable containing dev nsec for dev-nsec signer.",
    )
    sign_parser.set_defaults(func=run_sign)

    subscribe_parser = subparsers.add_parser("subscribe", help="Subscribe to relay events")
    subscribe_parser.add_argument(
        "--relay",
        default=None,
        help="Relay websocket URL (ws:// or wss://). Falls back to env if omitted.",
    )
    subscribe_parser.add_argument(
        "--kind",
        type=int,
        default=33301,
        help="Event kind to subscribe to (default: 33301).",
    )
    subscribe_parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help=(
            "Stop after receiving this many matching events (default: 1). "
            "Use 0 for stream until timeout/interrupt."
        ),
    )
    subscribe_parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Relay connect/receive timeout in seconds (default: 8.0).",
    )
    subscribe_parser.set_defaults(func=run_subscribe)

    index_parser = subparsers.add_parser(
        "index",
        help="Run indexer: subscribe to relay(s), reduce events, optionally persist to SQLite",
    )
    index_parser.add_argument(
        "--config",
        default=None,
        help=(
            "Optional path to OpenPrints TOML config "
            "(default: ./openprints.toml). "
            "CLI flags override config."
        ),
    )
    index_parser.add_argument(
        "--relay",
        action="append",
        default=None,
        help=(
            "Relay websocket URL; repeat flag for multiple relays. "
            "Falls back to env/config/default when omitted."
        ),
    )
    index_parser.add_argument(
        "--design-kind",
        type=int,
        default=None,
        dest="design_kind",
        help="Design event kind to ingest (falls back to env/config/default: 33301).",
    )
    index_parser.add_argument(
        "--design-queue-maxsize",
        type=int,
        default=None,
        dest="design_queue_maxsize",
        help="Design ingest queue max size (falls back to env/config/default: 1000).",
    )
    index_parser.add_argument(
        "--design-timeout-s",
        type=float,
        default=None,
        dest="design_timeout_s",
        help="Design relay timeout in seconds (env/config/default: 8.0).",
    )
    index_parser.add_argument(
        "--design-max-retries",
        type=int,
        default=None,
        dest="design_max_retries",
        help=(
            "Consecutive relay worker failures before giving up "
            "(falls back to env/config/default: 12, 0=infinite)."
        ),
    )
    index_parser.add_argument(
        "--design-duration-s",
        type=float,
        default=None,
        dest="design_duration_s",
        help="Run seconds before clean stop (falls back to env/config/default: 0=until interrupt).",
    )
    index_parser.set_defaults(func=run_index)

    serve_parser = subparsers.add_parser(
        "serve",
        help="Run HTTP API. Port from config api_port or OPENPRINTS_API_PORT (default 8080).",
    )
    serve_parser.add_argument(
        "--config",
        default=None,
        help="Path to OpenPrints TOML config (same as index command; used for database_path).",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind (default: config api_port or OPENPRINTS_API_PORT or 8080).",
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind (default: 0.0.0.0).",
    )
    serve_parser.add_argument(
        "--log-level",
        default="info",
        help="Uvicorn log level (default: info).",
    )
    serve_parser.set_defaults(func=run_serve)

    db_parser = subparsers.add_parser("db", help="Database operations")
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)
    stats_parser = db_sub.add_parser("stats", help="Print indexer DB stats and latest designs")
    stats_parser.add_argument(
        "--config",
        default=None,
        help="Path to OpenPrints TOML config (same as index command).",
    )
    stats_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max number of designs to list (default: 10, use 0 to skip list).",
    )
    stats_parser.set_defaults(func=run_db_stats)
    wipe_parser = db_sub.add_parser(
        "wipe",
        help="Wipe the indexer SQLite DB (requires --force)",
    )
    wipe_parser.add_argument(
        "--config",
        default=None,
        help="Path to OpenPrints TOML config (same as index command).",
    )
    wipe_parser.add_argument(
        "--force",
        action="store_true",
        help="Confirm wipe; required to avoid accidental data loss.",
    )
    wipe_parser.set_defaults(func=run_db_wipe)

    hash_parser = subparsers.add_parser("hash", help="Compute SHA-256 for a file or stdin")
    hash_parser.add_argument(
        "--file",
        default="-",
        help="Input file path, or '-' for stdin (default).",
    )
    hash_parser.set_defaults(func=run_hash)

    keygen_parser = subparsers.add_parser("keygen", help="Generate a local dev Nostr keypair")
    keygen_mode = keygen_parser.add_mutually_exclusive_group(required=False)
    keygen_mode.add_argument(
        "--json",
        action="store_true",
        help="Emit key material in JSON format.",
    )
    keygen_mode.add_argument(
        "--env",
        action="store_true",
        help="Emit only ENV assignment format (NAME=nsec...).",
    )
    keygen_parser.add_argument(
        "--env-name",
        default="OPENPRINTS_DEV_NSEC",
        help="Environment variable name used with --env output.",
    )
    keygen_parser.set_defaults(func=run_keygen)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return int(args.func(args))
