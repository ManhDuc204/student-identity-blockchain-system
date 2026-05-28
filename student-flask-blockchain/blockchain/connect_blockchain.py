import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import BadFunctionCallOutput
from web3.middleware import geth_poa_middleware

from .contract_config import get_chain_config
from .helpers_account import get_account_config, get_default_ganache_account, is_local_ganache
from .tx_utils import (
    detect_eip1559_support,
    build_eip1559_tx,
    build_legacy_tx,
    sign_and_send_raw_transaction,
    map_tx_exception,
)

# Load .env explicitly (repo-safe). If no .env exists, no crash.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
BUILD_CONTRACTS_DIR = BASE_DIR / "build" / "contracts"


# =========================
# WEB3 CONNECTION
# =========================

def get_web3() -> Web3:
    chain = get_chain_config()
    w3 = Web3(Web3.HTTPProvider(chain["rpc_url"]))

    # Ganache often doesn't need POA middleware, but leaving it is safe.
    try:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass

    if not w3.is_connected():
        raise RuntimeError(f"❌ Cannot connect to RPC: {chain['rpc_url']}")

    return w3


# =========================
# ARTIFACT LOADING + CONTRACT RESOLUTION
# =========================

def _load_truffle_artifact(contract_name: str) -> Dict[str, Any]:
    artifact_path = BUILD_CONTRACTS_DIR / f"{contract_name}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(
            f"❌ Missing Truffle artifact: {artifact_path}\n"
            f"👉 Run: npx truffle compile"
        )

    with open(artifact_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _abi_functions_detected(abi: list) -> list:
    if not isinstance(abi, list):
        return []

    out = []
    for item in abi:
        if item.get("type") != "function":
            continue
        name = item.get("name")
        if not name:
            continue
        inputs = item.get("inputs") or []
        input_types = ",".join((i.get("type") or "") for i in inputs)
        out.append(f"{name}({input_types})")
    return sorted(set(out))


def get_contract() -> Tuple[Any, Dict[str, Any]]:
    """Load contract by runtime chain_id + latest deployed address from Truffle artifact."""

    contract_name = "StudentIdentity"

    w3: Optional[Web3] = None
    latest_block: Optional[int] = None
    contract_address: Optional[str] = None

    try:
        w3 = get_web3()
        latest_block = w3.eth.block_number

        loaded = _load_truffle_artifact(contract_name)

        # Support multiple artifact shapes:
        # 1) {"artifact": {...}, "abi": [...]} (older internal helper format)
        # 2) Truffle/solc artifact directly: {"abi": [...], "bytecode": "...", "networks": {...}}
        if isinstance(loaded, dict) and "artifact" in loaded and "abi" in loaded:
            artifact = loaded["artifact"]
            abi = loaded["abi"]
        else:
            artifact = loaded
            abi = loaded.get("abi")


        chain_id = w3.eth.chain_id
        network_key = str(chain_id)
        networks = artifact.get("networks") or {}

        if network_key not in networks:
            if len(networks) == 1:
                (_, network_obj) = next(iter(networks.items()))
            else:
                raise ValueError(
                    "Contract address not found for current chain_id in artifact. "
                    f"artifact network keys={list(networks.keys())} current chain_id={chain_id}. "
                    "Ganache might have been reset or you need to redeploy. "
                    "Please run: npx truffle migrate --reset"
                )
        else:
            network_obj = networks[network_key]

        contract_address = network_obj.get("address")
        if not contract_address:
            raise ValueError(
                "Artifact networks entry missing address for current chain_id. "
                "Please run: npx truffle migrate --reset"
            )

        contract_address = Web3.to_checksum_address(contract_address)

        bytecode = w3.eth.get_code(contract_address)
        bytecode_length = len(bytecode) if bytecode is not None else 0

        # Strict triage as required by task: if networks[chain_id] address is stale, fail loudly.
        if bytecode_length == 0:
            artifact_network_keys = sorted(list((artifact.get("networks") or {}).keys()))
            expected_addr = network_obj.get("address")
            selected_addr_raw = expected_addr
            raise RuntimeError(
                "Artifact address stale or Ganache reset detected. "
                f"\n- chain_id={chain_id} "
                f"\n- rpc={get_chain_config().get('rpc_url')} "
                f"\n- artifact networks keys={artifact_network_keys} "
                f"\n- selected_address={selected_addr_raw} (checksum={contract_address}) "
                f"\n- bytecode_length={bytecode_length} "
                "\nAction: run npx truffle migrate --reset --verbose and ensure build/contracts/StudentIdentity.json contains networks['1337'].address"
            )



        # ABI mismatch validation requirement
        if not any(
            item.get("type") == "function" and item.get("name") == "getStudentHash" for item in abi
        ):
            get_funcs = [
                item.get("name")
                for item in abi
                if item.get("type") == "function" and item.get("name")
            ]
            raise ValueError(
                "ABI mismatch: missing getStudentHash(string). "
                f"Functions in ABI: {sorted(set(get_funcs))}"
            )

        abi_functions = _abi_functions_detected(abi)
        print(
            "[get_contract] debug snapshot: "
            f"chain_id={chain_id} contract_address={contract_address} latest_block={latest_block} "
            f"bytecode_length={len(bytecode) if bytecode is not None else None} "
            f"ABI functions detected={abi_functions}"
        )

        contract = w3.eth.contract(address=contract_address, abi=abi)
        debug_info = {
            "chain_id": chain_id,
            "contract_address": contract_address,
            "latest_block": latest_block,
            "bytecode_length": len(bytecode) if bytecode is not None else None,
            "abi_functions_detected": abi_functions,
        }
        return contract, debug_info

    except Exception:
        # best-effort logging
        try:
            if w3 is not None:
                chain_id = None
                try:
                    chain_id = w3.eth.chain_id
                except Exception:
                    chain_id = None

                code_len = None
                if contract_address:
                    try:
                        code_len = len(w3.eth.get_code(contract_address))
                    except Exception:
                        code_len = None

                print(
                    "[get_contract] ERROR debug: "
                    f"chain_id={chain_id} contract_address={contract_address} latest_block={latest_block} "
                    f"bytecode_length={code_len}"
                )
        except Exception:
            pass
        raise


# =========================
# VALIDATIONS
# =========================

def _validate_student_id(student_id: Any) -> str:
    if student_id is None:
        raise ValueError("student_id is None")
    s = str(student_id).strip()
    if not s:
        raise ValueError("student_id is empty")
    return s


def _validate_bytes32(value: Any) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        if len(value) != 32:
            raise ValueError("dataHash must be exactly 32 bytes")
        return bytes(value)

    if isinstance(value, str):
        v = value.lower().replace("0x", "")
        if len(v) != 64:
            raise ValueError("dataHash hex must be 64 hex chars")
        return Web3.to_bytes(hexstr=v)

    raise ValueError("dataHash must be bytes or hex string")


# =========================
# TX MODES
# =========================

def _tx_mode_and_account(w3: Web3) -> Tuple[str, str, Optional[str]]:
    """Return (tx_mode, checksum_address, private_key_or_none)."""
    chain = get_chain_config()
    local = is_local_ganache(chain.get("rpc_url"))

    cfg = get_account_config(w3)
    checksum_address = str(cfg["checksum_address"])
    private_key = cfg.get("private_key")

    # enforce local preference: always use ganache accounts[0] if local
    if local:
        # never depend on env address for demo stability
        addr0, _src = get_default_ganache_account(w3)
        checksum_address = str(Web3.to_checksum_address(addr0))
        private_key = None  # transact mode
        tx_mode = "transact"
    else:
        # production: require private key
        if not private_key:
            raise ValueError(
                "Missing PRIVATE_KEY (production mode requires sign_transaction/send_raw_transaction)."
            )
        tx_mode = "private_key_mode"

    return tx_mode, checksum_address, private_key


def _receipt_or_raise(w3: Web3, receipt):
    if receipt is None:
        raise RuntimeError("No receipt returned")

    status = getattr(receipt, "status", None)
    tx_hash = getattr(receipt, "transactionHash", None)
    block_number = getattr(receipt, "blockNumber", None)
    gas_used = getattr(receipt, "gasUsed", None)

    if status not in (1, None):
        # include revert reason if available (Ganache sometimes doesn't provide it)
        raise RuntimeError(
            "Transaction failed (receipt.status!=1). "
            f"status={status} tx_hash={tx_hash.hex() if tx_hash is not None else tx_hash} "
            f"blockNumber={block_number} gasUsed={gas_used}"
        )

    return receipt


def _build_and_send_local_tx(w3: Web3, tx: dict) -> Any:
    tx_hash = w3.eth.send_transaction(tx)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    return _receipt_or_raise(w3, receipt)


def _add_student_local(contract, w3: Web3, tx_from: str, student_id: str, data_hash_bytes32: bytes):
    fn = contract.functions.addStudent(student_id, data_hash_bytes32)
    chain_id = w3.eth.chain_id

    # pending nonce for stability under rapid consecutive txs
    nonce = w3.eth.get_transaction_count(tx_from, "pending")

    # fee config + tx builder (explicit)
    eip1559_supported = detect_eip1559_support(w3)
    latest = w3.eth.get_block("latest")
    base_fee = int(latest.get("baseFeePerGas")) if latest and latest.get("baseFeePerGas") is not None else None

    priority_fee = None
    max_fee = None

    if eip1559_supported:
        # build tx with EIP-1559 helpers but keep the local flow explicit
        # build_eip1559_tx uses safe_priority_fee_wei internally
        tx = build_eip1559_tx(
            w3,
            fn,
            from_addr=tx_from,
            nonce=nonce,
            chain_id=chain_id,
        )
        max_fee = tx.get("maxFeePerGas")
        priority_fee = tx.get("maxPriorityFeePerGas")
    else:
        tx = build_legacy_tx(
            w3,
            fn,
            from_addr=tx_from,
            nonce=nonce,
            chain_id=chain_id,
        )
        # legacy fee has gasPrice
        # keep debug fields consistent

    print(
        "[tx-debug-local] addStudent "
        f"chainId={chain_id} from={tx_from} tx_mode=transact "
        f"nonce(pending)={nonce} "
        f"baseFeePerGas={base_fee} "
        f"maxFeePerGas={max_fee} maxPriorityFeePerGas={priority_fee} "
    )

    return _build_and_send_local_tx(w3, tx)


def _add_student_private_key(contract, w3: Web3, tx_from: str, private_key: str, student_id: str, data_hash_bytes32: bytes):
    fn = contract.functions.addStudent(student_id, data_hash_bytes32)
    chain_id = w3.eth.chain_id
    nonce = w3.eth.get_transaction_count(tx_from)

    eip1559_supported = detect_eip1559_support(w3)
    print(
        "[tx-flow/prod] addStudent "
        f"nonce={nonce} chainId={chain_id} from={tx_from} eip1559_supported={eip1559_supported}"
    )

    if eip1559_supported:
        tx = build_eip1559_tx(
            w3,
            fn,
            from_addr=tx_from,
            nonce=nonce,
            chain_id=chain_id,
        )
    else:
        tx = build_legacy_tx(
            w3,
            fn,
            from_addr=tx_from,
            nonce=nonce,
            chain_id=chain_id,
        )

    receipt = sign_and_send_raw_transaction(w3, tx, private_key)
    return receipt


def _delete_student_local(contract, w3: Web3, tx_from: str, student_id: str):
    fn = contract.functions.logDeletion(student_id)
    chain_id = w3.eth.chain_id

    nonce = w3.eth.get_transaction_count(tx_from, "pending")

    eip1559_supported = detect_eip1559_support(w3)
    latest = w3.eth.get_block("latest")
    base_fee = int(latest.get("baseFeePerGas")) if latest and latest.get("baseFeePerGas") is not None else None

    priority_fee = None
    max_fee = None

    if eip1559_supported:
        tx = build_eip1559_tx(
            w3,
            fn,
            from_addr=tx_from,
            nonce=nonce,
            chain_id=chain_id,
        )
        max_fee = tx.get("maxFeePerGas")
        priority_fee = tx.get("maxPriorityFeePerGas")
    else:
        tx = build_legacy_tx(
            w3,
            fn,
            from_addr=tx_from,
            nonce=nonce,
            chain_id=chain_id,
        )

    print(
        "[tx-debug-local] logDeletion "
        f"chainId={chain_id} from={tx_from} tx_mode=transact "
        f"nonce(pending)={nonce} "
        f"baseFeePerGas={base_fee} "
        f"maxFeePerGas={max_fee} maxPriorityFeePerGas={priority_fee} "
    )

    return _build_and_send_local_tx(w3, tx)


def _delete_student_private_key(contract, w3: Web3, tx_from: str, private_key: str, student_id: str):
    fn = contract.functions.logDeletion(student_id)
    chain_id = w3.eth.chain_id
    nonce = w3.eth.get_transaction_count(tx_from)

    eip1559_supported = detect_eip1559_support(w3)
    print(
        "[tx-flow/prod] logDeletion "
        f"nonce={nonce} chainId={chain_id} from={tx_from} eip1559_supported={eip1559_supported}"
    )

    if eip1559_supported:
        tx = build_eip1559_tx(
            w3,
            fn,
            from_addr=tx_from,
            nonce=nonce,
            chain_id=chain_id,
        )
    else:
        tx = build_legacy_tx(
            w3,
            fn,
            from_addr=tx_from,
            nonce=nonce,
            chain_id=chain_id,
        )

    receipt = sign_and_send_raw_transaction(w3, tx, private_key)
    return receipt


# =========================
# PUBLIC TX API
# =========================

def _bytes32_to_hex_no0x(b: Any) -> str:
    if b is None:
        return ""
    if isinstance(b, (bytes, bytearray)):
        return bytes(b).hex().lower()
    s = str(b)
    return s.replace("0x", "").lower()


def send_add_student_tx(student_id: str, data_hash_hex: str):
    w3 = get_web3()
    contract, debug = get_contract()

    tx_mode, from_addr, private_key = _tx_mode_and_account(w3)
    chain_id = debug.get("chain_id")
    deployed = debug.get("contract_address")
    bytecode_len = debug.get("bytecode_length")

    # additional required debug fields
    try:
        latest = w3.eth.get_block("latest")
        base_fee = latest.get("baseFeePerGas")
    except Exception:
        base_fee = None

    try:
        latest = w3.eth.get_block("latest")
        # detect_eip1559_support implies baseFeePerGas existence
        eip1559_supported = detect_eip1559_support(w3)
    except Exception:
        eip1559_supported = False

    print(
        "[tx-flow] connected="
        f"{w3.is_connected()} chain_id={chain_id} "
        f"selected_account={from_addr} tx_mode={tx_mode} "
        f"deployed_contract={deployed} bytecode_length={bytecode_len} "
        f"baseFeePerGas={base_fee} eip1559_supported={eip1559_supported}"
    )

    try:
        student_id = _validate_student_id(student_id)
        data_hash_bytes32 = _validate_bytes32(data_hash_hex)

        if tx_mode == "transact":
            receipt = _add_student_local(contract, w3, from_addr, student_id, data_hash_bytes32)
        else:
            receipt = _add_student_private_key(contract, w3, from_addr, private_key, student_id, data_hash_bytes32)

        # verify receipt fields + log details
        tx_hash = getattr(receipt, "transactionHash", None)
        block_number = getattr(receipt, "blockNumber", None)
        gas_used = getattr(receipt, "gasUsed", None)
        status = getattr(receipt, "status", None)

        print(
            "[tx-receipt] addStudent "
            f"tx_hash={tx_hash.hex() if tx_hash is not None else tx_hash} "
            f"blockNumber={block_number} gasUsed={gas_used} status={status}"
        )

        if status != 1:
            raise RuntimeError(
                "addStudent failed: receipt.status!=1 "
                f"status={status} tx_hash={tx_hash.hex() if tx_hash is not None else tx_hash} "
                f"blockNumber={block_number} gasUsed={gas_used}"
            )

        # on-chain verification after add
        onchain = contract.functions.getStudentHash(student_id).call()
        local_hex = _bytes32_to_hex_no0x(data_hash_bytes32)
        onchain_hex = _bytes32_to_hex_no0x(onchain)

        if onchain_hex == local_hex:
            print(f"[post-add-verify] OK student_id={student_id}")
        else:
            # required warning/error details
            print(
                "[post-add-verify] MISMATCH "
                f"student_id={student_id} localHash={local_hex} onchainHash={onchain_hex}"
            )
            raise RuntimeError(
                "On-chain hash mismatch after addStudent "
                f"student_id={student_id} localHash={local_hex} onchainHash={onchain_hex}"
            )

        return receipt
    except Exception as e:
        raise map_tx_exception(e)


def send_delete_student_tx(student_id: str):
    w3 = get_web3()
    contract, debug = get_contract()

    tx_mode, from_addr, private_key = _tx_mode_and_account(w3)
    print(
        "[tx-flow] connected="
        f"{w3.is_connected()} chain_id={debug.get('chain_id')} "
        f"selected_account={from_addr} tx_mode={tx_mode} "
        f"deployed_contract={debug.get('contract_address')} bytecode_length={debug.get('bytecode_length')}"
    )

    try:
        student_id = _validate_student_id(student_id)

        if tx_mode == "transact":
            receipt = _delete_student_local(contract, w3, from_addr, student_id)
        else:
            receipt = _delete_student_private_key(contract, w3, from_addr, private_key, student_id)

        return receipt
    except Exception as e:
        raise map_tx_exception(e)


# =========================
# READ ONCHAIN DATA
# =========================

def get_student_hash_onchain(student_id: Any):
    w3: Optional[Web3] = None
    try:
        student_id = _validate_student_id(student_id)

        w3 = get_web3()
        if not w3.is_connected():
            print("[get_student_hash_onchain] ERROR: Web3 not connected")
            return None

        contract, debug_info = get_contract()

        # validate deployed bytecode presence
        if debug_info.get("contract_address"):
            code = w3.eth.get_code(debug_info["contract_address"])
            if code == b"" or code is None:
                raise Exception(
                    "Contract not deployed at this address. Ganache may have been reset. "
                    "Please run: npx truffle migrate --reset"
                )

        try:
            return contract.functions.getStudentHash(student_id).call()
        except (BadFunctionCallOutput, ValueError) as e:
            print(
                "[get_student_hash_onchain] CALL FAILED: "
                f"student_id={student_id} debug={json.dumps(debug_info, default=str)} error={repr(e)}"
            )
            return None

    except Exception as e:
        debug_info = {}
        try:
            if w3 is not None:
                debug_info["chain_id"] = w3.eth.chain_id
                debug_info["latest_block"] = w3.eth.block_number
        except Exception:
            pass
        print(
            "[get_student_hash_onchain] ERROR: "
            f"student_id={student_id} debug={json.dumps(debug_info, default=str)} error={repr(e)}"
        )
        return None


# =========================
# BLOCK INFO / STATS
# =========================

def get_latest_block() -> Dict[str, Any]:
    w3 = get_web3()
    blk = w3.eth.get_block("latest")

    from datetime import datetime, timezone

    ts = blk.get("timestamp")
    timestamp_dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)

    return {**dict(blk), "timestamp_dt": timestamp_dt}


def get_stats() -> Dict[str, Any]:
    w3 = get_web3()
    return {"web3_connected": w3.is_connected(), "latest_block": w3.eth.block_number}

