import os
import re
from typing import Optional, Tuple

from web3 import Web3


def _is_placeholder(value: str) -> bool:
    v = value.strip().lower()
    return (
        v == "" or v in {"none", "null"}
        or "your_address" in v
        or "your_private_key" in v
        or "0xyour" in v
        or "0xplaceholder" in v
        or "placeholder" in v
    )


def validate_eth_address(addr: Optional[str], *, var_name: str = "ACCOUNT_ADDRESS") -> str:
    if addr is None:
        raise ValueError(f"Missing {var_name}")

    a = addr.strip()
    if _is_placeholder(a):
        raise ValueError(f"Invalid {var_name}: placeholder/empty value provided")

    if not a.startswith("0x"):
        raise ValueError(f"Invalid {var_name}: must start with 0x")

    if not Web3.is_address(a):
        raise ValueError(f"Invalid {var_name}: not a valid hex address: {addr}")

    return Web3.to_checksum_address(a)


def validate_private_key(private_key: Optional[str], *, var_name: str = "PRIVATE_KEY") -> str:
    if private_key is None:
        raise ValueError(f"Missing {var_name}")

    pk = private_key.strip()
    if _is_placeholder(pk):
        raise ValueError(f"Invalid {var_name}: placeholder/empty value provided")

    if pk.startswith("0x"):
        hex_body = pk[2:]
    else:
        raise ValueError(f"Invalid {var_name}: must start with 0x")

    if len(hex_body) != 64:
        raise ValueError(
            f"Invalid {var_name}: must be 64 hex chars after 0x (got {len(hex_body)})"
        )

    if not re.fullmatch(r"[0-9a-fA-F]{64}", hex_body):
        raise ValueError(f"Invalid {var_name}: contains non-hex characters")

    # Normalize
    return "0x" + hex_body.lower()


def derive_account_from_private_key(private_key: str) -> Tuple[str, str]:
    pk_norm = validate_private_key(private_key)
    acct = Web3().eth.account.from_key(pk_norm)
    return acct.address, pk_norm


def get_required_env(var_name: str) -> str:
    v = os.environ.get(var_name)
    if v is None:
        raise ValueError(f"Missing env var: {var_name}")
    return v

