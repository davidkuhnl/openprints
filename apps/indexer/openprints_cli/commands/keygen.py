from __future__ import annotations

import secrets
import sys
from argparse import Namespace

from bech32 import bech32_encode, convertbits
from coincurve import PrivateKey

from openprints_cli.utils.output import print_json


def _to_bech32(hrp: str, raw: bytes) -> str:
    data = convertbits(raw, 8, 5, True)
    if data is None:
        raise ValueError(f"failed to convert bytes for {hrp}")
    return bech32_encode(hrp, data)


def run_keygen(args: Namespace) -> int:
    secret = secrets.token_bytes(32)
    pubkey = PrivateKey(secret).public_key_xonly.format().hex()

    nsec = _to_bech32("nsec", secret)
    npub = _to_bech32("npub", bytes.fromhex(pubkey))

    if args.json:
        print_json(
            {
                "nsec": nsec,
                "npub": npub,
                "pubkey": pubkey,
                "env_var": args.env_name,
            }
        )
    elif args.env:
        print(f"{args.env_name}={nsec}")
    else:
        print("Generated dev keypair:")
        print(f"nsec: {nsec}")
        print(f"npub: {npub}")
        print(f"pubkey: {pubkey}")
        print(f"env: {args.env_name}={nsec}")

    print("keygen: dev key only, do not commit or share private keys.", file=sys.stderr)
    return 0
