from __future__ import annotations

import os

from openprints.common.signers.base import Signer, SignerError
from openprints.common.signers.dev_nsec import DevNsecSigner

SUPPORTED_SIGNERS = ("dev-nsec", "remote")


def build_signer(signer_name: str, nsec_env: str) -> Signer:
    if signer_name == "dev-nsec":
        nsec_value = os.environ.get(nsec_env, "").strip()
        if not nsec_value:
            raise SignerError(f"missing signer key: set environment variable {nsec_env}")
        return DevNsecSigner.from_nsec(nsec_value)

    if signer_name == "remote":
        raise SignerError("remote signer backend is not implemented yet")

    raise SignerError(f"unsupported signer backend: {signer_name}")
