import argparse

from .commands.build import run_build
from .commands.hash import run_hash
from .commands.index import run_index
from .commands.keygen import run_keygen
from .commands.publish import run_publish
from .commands.sign import run_sign
from .commands.subscribe import run_subscribe
from .signers.factory import SUPPORTED_SIGNERS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openprints-cli")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="Build a design event payload")
    build_parser.add_argument("--name", required=True, help="Human-readable design name.")
    build_parser.add_argument(
        "--design-id",
        default=None,
        help="Optional design id (uuid or openprints:uuid). If omitted, a uuid-v4 is generated.",
    )
    build_parser.add_argument(
        "--format", required=True, help="Design file format (for example stl)."
    )
    build_parser.add_argument(
        "--url", required=True, help="Public URL where the design file is hosted."
    )
    build_parser.add_argument(
        "--content",
        default="",
        help="Optional Markdown description to include in event.content.",
    )
    build_hash_input = build_parser.add_mutually_exclusive_group(required=True)
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
    build_parser.add_argument(
        "--output",
        default="-",
        help="Output path for payload JSON, or '-' for stdout (default).",
    )
    build_parser.set_defaults(func=run_build)

    publish_parser = subparsers.add_parser("publish", help="Publish an event to relay(s)")
    publish_parser.add_argument(
        "--input",
        default="-",
        help="Input path for payload JSON, or '-' for stdin (default).",
    )
    publish_parser.add_argument(
        "--relay",
        default=None,
        help="Relay websocket URL (ws:// or wss://). Falls back to env if omitted.",
    )
    publish_parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Relay connect/ack timeout in seconds (default: 8.0).",
    )
    publish_parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Number of retry attempts for transport/timeouts (default: 0).",
    )
    publish_parser.add_argument(
        "--retry-backoff-ms",
        type=int,
        default=400,
        help="Delay between retry attempts in milliseconds (default: 400).",
    )
    publish_parser.set_defaults(func=run_publish)

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
        help="Run indexer ingestion pipeline stub (no DB writes yet)",
    )
    index_parser.add_argument(
        "--config",
        default=None,
        help=(
            "Optional path to indexer TOML config (default: ./openprints.indexer.toml "
            "if present). CLI flags override config."
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
        "--kind",
        type=int,
        default=None,
        help="Event kind to ingest (falls back to env/config/default: 33301).",
    )
    index_parser.add_argument(
        "--queue-maxsize",
        type=int,
        default=None,
        help="Shared ingest queue max size (falls back to env/config/default: 1000).",
    )
    index_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Relay receive/connect timeout in seconds (falls back to env/config/default: 8.0).",
    )
    index_parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help=(
            "Consecutive relay worker failures before giving up "
            "(falls back to env/config/default: 12, 0=infinite)."
        ),
    )
    index_parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Run seconds before clean stop (falls back to env/config/default: 0=until interrupt).",
    )
    index_parser.set_defaults(func=run_index)

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
