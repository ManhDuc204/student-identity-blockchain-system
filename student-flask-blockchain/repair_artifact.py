import json
import os
import subprocess
import sys
from pathlib import Path

from web3 import Web3


REPO_DIR = Path(__file__).resolve().parent
BUILD_CONTRACTS_DIR = REPO_DIR / "build" / "contracts"
CONTRACT_NAME = "StudentIdentity"
ARTIFACT_PATH = BUILD_CONTRACTS_DIR / f"{CONTRACT_NAME}.json"


def run(cmd: str) -> None:
    print(f"\n[run] {cmd}")
    proc = subprocess.run(cmd, shell=True, cwd=str(REPO_DIR), capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise RuntimeError(f"Command failed (code={proc.returncode}): {cmd}")


def load_artifact() -> dict:
    if not ARTIFACT_PATH.exists():
        raise FileNotFoundError(f"Missing artifact: {ARTIFACT_PATH}")
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


def resolve_address_and_verify(w3: Web3, artifact: dict) -> None:
    chain_id = int(w3.eth.chain_id)
    network_key = str(chain_id)

    networks = artifact.get("networks") or {}
    if network_key not in networks:
        if len(networks) == 1:
            (_, network_obj) = next(iter(networks.items()))
        else:
            raise RuntimeError(
                "Artifact networks does not contain current chain_id. "
                f"chain_id={chain_id} artifact_network_keys={sorted(networks.keys())}"
            )
    else:
        network_obj = networks[network_key]

    addr = network_obj.get("address")
    if not addr:
        raise RuntimeError(f"Artifact networks entry missing address for chain_id={chain_id}")

    addr = Web3.to_checksum_address(addr)
    bytecode = w3.eth.get_code(addr)
    if bytecode is None or bytecode == b"":
        raise RuntimeError(
            "Deployed bytecode empty at resolved address. "
            f"chain_id={chain_id} address={addr}. "
            "Ganache might have been reset; run: npx truffle migrate --reset --verbose"
        )

    # ABI sanity checks
    abi = artifact.get("abi")
    if not isinstance(abi, list):
        raise RuntimeError("Artifact missing abi[]")

    def has_fn(name: str, input_types_prefix: str | None = None) -> bool:
        for item in abi:
            if item.get("type") != "function":
                continue
            if item.get("name") != name:
                continue
            if input_types_prefix is None:
                return True
            inputs = item.get("inputs") or []
            types = [i.get("type") for i in inputs]
            joined = ",".join(types)
            return joined.startswith(input_types_prefix)
        return False

    # addStudent(string,bytes32) and getStudentHash(string)
    if not has_fn("addStudent"):
        raise RuntimeError("ABI missing addStudent function")
    if not has_fn("getStudentHash"):
        raise RuntimeError("ABI missing getStudentHash function")

    print("\n=== repair_artifact.py: OK ===")
    print(f"chain_id={chain_id}")
    print(f"resolved_contract_address={addr}")
    print(f"deployed_bytecode_length={len(bytecode)}")


def main():
    rpc_url = os.environ.get("RPC_URL", "http://127.0.0.1:7545")

    # Must follow user requested commands
    run("npx truffle compile --all")
    run("npx truffle migrate --reset --verbose")

    artifact = load_artifact()

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to RPC: {rpc_url}")

    resolve_address_and_verify(w3, artifact)


if __name__ == "__main__":
    main()

