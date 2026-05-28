import os
import re
from typing import Any, Dict, Optional, Tuple

from web3 import Web3

from .contract_config import get_chain_config


def detect_eip1559_support(w3: Web3) -> bool:
    """Return True if latest block exposes baseFeePerGas (London-style)."""
    try:
        blk = w3.eth.get_block("latest")
        return blk is not None and ("baseFeePerGas" in blk and blk["baseFeePerGas"] is not None)
    except Exception:
        return False


def safe_priority_fee_wei(w3: Web3) -> int:
    """Pick maxPriorityFeePerGas.

    Uses env override TX_MAX_PRIORITY_FEE_WEI if set.
    Otherwise falls back to 2 gwei.
    """
    pwei = os.environ.get("TX_MAX_PRIORITY_FEE_WEI")
    if pwei:
        return int(pwei)
    return w3.to_wei(2, "gwei")


def build_eip1559_tx(
    w3: Web3,
    fn,
    *,
    from_addr: str,
    nonce: int,
    chain_id: int,
    gas_limit: Optional[int] = None,
    gas_multiplier_bps: int = 12000,
) -> Dict[str, Any]:
    """Build EIP-1559 tx ensuring maxFeePerGas >= baseFeePerGas."""

    latest = w3.eth.get_block("latest")
    base_fee = int(latest["baseFeePerGas"])
    priority_fee = int(safe_priority_fee_wei(w3))
    max_fee = base_fee + priority_fee * 2

    if max_fee < base_fee:
        # Hard stop: this is exactly the failure we want to prevent.
        raise ValueError(
            f"Computed maxFeePerGas({max_fee}) < baseFeePerGas({base_fee}). "
            "Check priority fee / base fee." 
        )

    if gas_limit is None:
        estimated_gas = int(
            fn.estimate_gas(
                {
                    "from": from_addr,
                    "nonce": nonce,
                    "chainId": chain_id,
                    "maxFeePerGas": max_fee,
                    "maxPriorityFeePerGas": priority_fee,
                }
            )
        )
        # default: +20% margin (12000 bps)
        gas_limit = int(estimated_gas * gas_multiplier_bps / 10000)
    else:
        estimated_gas = None

    tx = fn.build_transaction(
        {
            "from": from_addr,
            "nonce": nonce,
            "gas": int(gas_limit),
            "chainId": chain_id,
            "maxFeePerGas": int(max_fee),
            "maxPriorityFeePerGas": int(priority_fee),
        }
    )

    # Debug logs required
    print(
        "[tx-debug-eip1559] "
        f"baseFeePerGas={base_fee} "
        f"maxPriorityFeePerGas={priority_fee} "
        f"maxFeePerGas={max_fee} "
        f"estimatedGas={estimated_gas} "
        f"gasLimit={gas_limit} "
        f"nonce={nonce} "
        f"chainId={chain_id} "
        f"from={from_addr}"
    )

    return tx


def build_legacy_tx(
    w3: Web3,
    fn,
    *,
    from_addr: str,
    nonce: int,
    chain_id: int,
    gas_limit: Optional[int] = None,
    gas_multiplier_bps: int = 12000,
) -> Dict[str, Any]:
    """Build legacy tx using gasPrice (fallback if EIP-1559 unsupported)."""

    gas_price = int(w3.eth.gas_price)
    if gas_limit is None:
        estimated_gas = int(fn.estimate_gas({"from": from_addr, "nonce": nonce, "chainId": chain_id}))
        gas_limit = int(estimated_gas * gas_multiplier_bps / 10000)
    else:
        estimated_gas = None

    tx = fn.build_transaction(
        {
            "from": from_addr,
            "nonce": nonce,
            "gas": int(gas_limit),
            "chainId": chain_id,
            "gasPrice": gas_price,
        }
    )

    print(
        "[tx-debug-legacy] "
        f"gasPrice={gas_price} estimatedGas={estimated_gas} gasLimit={gas_limit} "
        f"nonce={nonce} chainId={chain_id} from={from_addr}"
    )

    return tx


def sign_and_send_raw_transaction(w3: Web3, tx: Dict[str, Any], private_key: str):
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    return receipt


def map_tx_exception(e: Exception) -> Exception:
    msg = str(e).lower()

    # Common ganache / geth messages
    if "insufficient funds" in msg:
        return RuntimeError(f"Transaction failed: insufficient funds: {e}")

    if "replacement transaction underpriced" in msg:
        return RuntimeError(f"Transaction failed: replacement transaction underpriced: {e}")

    if "nonce too low" in msg or "nonce is too low" in msg:
        return RuntimeError(f"Transaction failed: nonce too low: {e}")

    # under/fee related
    if "fee too low" in msg or re.search(r"max.*fee.*less", msg):
        return RuntimeError(f"Transaction failed: fee too low: {e}")

    return e

