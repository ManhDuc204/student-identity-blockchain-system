from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from web3 import Web3
from web3.types import ChecksumAddress


def _is_placeholder(value: Optional[str]) -> bool:
    if value is None:
        return True
    v = str(value).strip().lower()
    return (
        v == "" or v in {"none", "null"}
        or "your_address" in v
        or "your_private_key" in v
        or "0xyour" in v
        or "0xplaceholder" in v
        or "placeholder" in v
    )


def is_local_ganache(rpc_url: str | None) -> bool:
    if not rpc_url:
        return False
    return str(rpc_url).startswith("http://127.0.0.1") or str(rpc_url).startswith("http://localhost")


def get_default_ganache_account(w3: Web3) -> tuple[ChecksumAddress, str]:
    """Return (checksum_address, source_tag)."""
    accounts = w3.eth.accounts
    if not accounts:
        raise RuntimeError("Ganache local mode: w3.eth.accounts is empty")
    addr = Web3.to_checksum_address(accounts[0])
    return addr, "fallback_ganache"


def _validate_private_key_format(pk: str) -> str:
    if _is_placeholder(pk):
        raise ValueError("PRIVATE_KEY placeholder/empty provided")
    pk = pk.strip()
    if not pk.startswith("0x"):
        raise ValueError("PRIVATE_KEY must start with 0x")
    hex_body = pk[2:]
    if len(hex_body) != 64:
        raise ValueError(f"PRIVATE_KEY must be 64 hex chars after 0x (got {len(hex_body)})")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", hex_body):
        raise ValueError("PRIVATE_KEY contains non-hex characters")
    return "0x" + hex_body.lower()


def get_account_config(w3: Web3) -> Dict[str, Any]:
    """Return account configuration for tx.

    Required outputs:
      - account_address
      - private_key
      - checksum_address
      - source(env/fallback/private_key)

    Rules:
      - Local Ganache: prefer transact mode (private_key may be None)
      - If PRIVATE_KEY is valid, derive address from it
      - If ACCOUNT_ADDRESS is valid, use it
      - Never hard crash on placeholder ACCOUNT_ADDRESS: fallback to w3.eth.accounts[0]
    """

    from .contract_config import get_chain_config

    chain = get_chain_config()
    rpc_url = chain.get("rpc_url")
    local = is_local_ganache(rpc_url)

    raw_account_address = chain.get("account_address")
    raw_private_key = chain.get("private_key")

    selected_address: Optional[ChecksumAddress] = None
    selected_private_key: Optional[str] = None
    source = "none"

    debug: Dict[str, Any] = {
        "rpc_url": rpc_url,
        "is_local_ganache": local,
        "raw_ACCOUNT_ADDRESS": raw_account_address,
        "raw_PRIVATE_KEY_present": bool(raw_private_key),
    }

    # 1) Try env ACCOUNT_ADDRESS if provided and looks non-placeholder
    if raw_account_address and not _is_placeholder(raw_account_address):
        try:
            if not Web3.is_address(str(raw_account_address)):
                raise ValueError("ACCOUNT_ADDRESS is not a valid address")
            selected_address = Web3.to_checksum_address(str(raw_account_address))
            source = "env"
        except Exception:
            selected_address = None
            source = "none"

    # 2) If PRIVATE_KEY exists and isn't placeholder: validate + derive
    if raw_private_key and not _is_placeholder(raw_private_key):
        try:
            pk_norm = _validate_private_key_format(str(raw_private_key))
            acct = Web3().eth.account.from_key(pk_norm)
            derived = Web3.to_checksum_address(acct.address)

            # If env address exists, ensure it matches
            if selected_address is not None and selected_address != derived:
                # keep production safe: mismatch => fail if not local
                if not local:
                    raise ValueError(f"PRIVATE_KEY does not match ACCOUNT_ADDRESS: {derived} vs {selected_address}")
                # local safe: prefer Ganache account later
                selected_address = None
                source = "none"

            # in local, we may still avoid raw tx; but derived address is useful for transact mode.
            selected_address = derived
            selected_private_key = pk_norm
            source = "private_key"
        except Exception as e:
            if not local:
                raise
            # local safe: ignore private key issues
            debug["private_key_error"] = str(e)

    # 3) If still no valid address, fallback to Ganache account 0
    if selected_address is None:
        fallback_addr, src_tag = get_default_ganache_account(w3)
        selected_address = fallback_addr
        selected_private_key = None if local else selected_private_key
        source = src_tag

    # production-safe: address validation
    if not Web3.is_address(selected_address):
        raise ValueError(f"Selected account is not a valid address: {selected_address}")

    # requirement: return checksum address
    checksum_address = Web3.to_checksum_address(selected_address)

    return {
        "account_address": str(checksum_address),
        "private_key": selected_private_key,
        "checksum_address": checksum_address,
        "source": source,
        "debug": debug,
        "tx_mode": "transact" if local else "private_key_mode" if selected_private_key else "transact",
    }

