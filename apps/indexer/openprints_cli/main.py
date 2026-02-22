import argparse

from .commands.build import run_build
from .commands.hash import run_hash
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
    subscribe_parser.set_defaults(func=run_subscribe)

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
