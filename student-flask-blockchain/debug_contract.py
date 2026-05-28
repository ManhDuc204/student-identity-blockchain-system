import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from web3 import Web3
from web3.exceptions import BadFunctionCallOutput
from web3.middleware import geth_poa_middleware


BASE_DIR = Path(__file__).resolve().parent
BUILD_DIR = BASE_DIR / "build" / "contracts"


def _connect_web3(rpc_url: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to RPC: {rpc_url}")
    return w3


def _load_truffle_artifact(contract_name: str) -> Dict[str, Any]:
    artifact_path = BUILD_DIR / f"{contract_name}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Missing Truffle artifact: {artifact_path}\nRun: npx truffle compile")
    with open(artifact_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _abi_functions_detected(abi: list) -> List[str]:
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


def _get_deployed_contract_from_artifact(w3: Web3, artifact: Dict[str, Any]):
    chain_id = w3.eth.chain_id
    networks = artifact.get("networks") or {}
    key = str(chain_id)

    # Try direct match first. If not found, and there's only one network entry,
    # fall back to that single deployed address.
    if key not in networks:
        if len(networks) == 1:
            (key, network_obj) = next(iter(networks.items()))
        else:
            raise ValueError(
                "Artifact does not have current chain_id. "
                f"artifact network keys={list(networks.keys())} current chain_id={w3.eth.chain_id}. "
                "Ganache may have been reset or you need to redeploy. "
                "Please run: npx truffle migrate --reset"
            )
    else:
        network_obj = networks[key]

    contract_address = network_obj.get("address")
    if not contract_address:
        raise ValueError(
            "Artifact networks entry has no address for this chain_id. "
            "Please run: npx truffle migrate --reset"
        )

    contract_address = Web3.to_checksum_address(contract_address)

    abi = artifact.get("abi")
    if not isinstance(abi, list) or not abi:
        raise ValueError("ABI missing or invalid in artifact")

    code = w3.eth.get_code(contract_address)
    print("\n=== Contract deployed bytecode ===")
    print("contract_address:", contract_address)
    print("bytecode_length:", len(code) if code is not None else None)

    if code == b"" or code is None:
        raise Exception(
            "Contract not deployed at this address. Ganache may have been reset. "
            "Please run: npx truffle migrate --reset"
        )

    contract = w3.eth.contract(address=contract_address, abi=abi)
    return contract, chain_id, contract_address, code, abi


def main() -> None:
    student_id = sys.argv[1] if len(sys.argv) > 1 else "SV001"

    contract_name = "StudentIdentity"
    rpc_url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:7545"

    print("=== debug_contract.py ===")
    print("student_id:", student_id)
    print("contract_name:", contract_name)
    print("rpc_url:", rpc_url)

    artifact = _load_truffle_artifact(contract_name)
    abi = artifact.get("abi")

    print("\n=== ABI functions detected ===")
    if isinstance(abi, list):
        for f in _abi_functions_detected(abi):
            print("-", f)
    else:
        print("ABI invalid/missing")

    if not isinstance(abi, list) or not any(
        item.get("type") == "function" and item.get("name") == "getStudentHash" for item in abi
    ):
        raise ValueError("ABI mismatch: missing getStudentHash(string)")

    w3 = _connect_web3(rpc_url)

    latest_block = w3.eth.block_number
    print("\n=== Chain snapshot ===")
    print("chain_id:", w3.eth.chain_id)
    print("latest_block:", latest_block)

    contract, chain_id, contract_address, code, abi = _get_deployed_contract_from_artifact(w3, artifact)

    print("\n=== Attempt call getStudentHash ===")
    try:
        value = contract.functions.getStudentHash(student_id).call()
        if isinstance(value, (bytes, bytearray)):
            print("call_success: True")
            print("result_bytes32:", value)
            print("result_hex:", Web3.to_hex(value))
        else:
            print("call_success: True")
            print("result:", value)
    except BadFunctionCallOutput as e:
        print("call_success: False")
        print("BadFunctionCallOutput:", str(e))
        print(
            "debug_details:\n",
            json.dumps(
                {
                    "error": str(e),
                    "student_id": student_id,
                    "chain_id": chain_id,
                    "latest_block": latest_block,
                    "contract_address": contract_address,
                    "bytecode_length": len(code),
                },
                default=str,
                indent=2,
            ),
        )
        raise
    except Exception as e:
        print("call_success: False")
        print("Exception:", repr(e))
        print(
            "debug_details:\n",
            json.dumps(
                {
                    "error": str(e),
                    "student_id": student_id,
                    "chain_id": chain_id,
                    "latest_block": latest_block,
                    "contract_address": contract_address,
                    "bytecode_length": len(code),
                },
                default=str,
                indent=2,
            ),
        )
        raise


if __name__ == "__main__":
    main()

