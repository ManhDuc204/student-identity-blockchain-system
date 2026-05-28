import json
from pathlib import Path

from web3 import Web3


REPO_DIR = Path(__file__).resolve().parent
BASE_DIR = REPO_DIR
BUILD_CONTRACTS_DIR = BASE_DIR / "build" / "contracts"
CONTRACT_NAME = "StudentIdentity"


def _load_truffle_artifact() -> dict:
    artifact_path = BUILD_CONTRACTS_DIR / f"{CONTRACT_NAME}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Missing artifact: {artifact_path}. Run: npx truffle compile --all")
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def _resolve_contract_address(w3: Web3, artifact: dict) -> str:
    chain_id = int(w3.eth.chain_id)
    network_key = str(chain_id)

    networks = (artifact.get("networks") or {})

    if network_key not in networks:
        if len(networks) == 1:
            # best-effort if chain_id differs but only one network entry exists
            (_, network_obj) = next(iter(networks.items()))
        else:
            raise RuntimeError(
                "Artifact networks does not contain current chain_id. "
                f"chain_id={chain_id} artifact_network_keys={sorted(networks.keys())}. "
                "Run: npx truffle migrate --reset --verbose"
            )
    else:
        network_obj = networks[network_key]

    addr = network_obj.get("address")
    if not addr:
        raise RuntimeError(f"Artifact networks entry missing address for chain_id={chain_id}")
    return Web3.to_checksum_address(addr)


def main():
    rpc_url = "http://127.0.0.1:7545"
    # allow override
    import os

    rpc_url = os.environ.get("RPC_URL", rpc_url)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to RPC: {rpc_url}")

    chain_id = int(w3.eth.chain_id)
    try:
        net_version = w3.net.version
    except Exception:
        net_version = None

    artifact = _load_truffle_artifact()
    contract_address = _resolve_contract_address(w3, artifact)
    bytecode = w3.eth.get_code(contract_address)

    try:
        accounts0 = w3.eth.accounts[0] if hasattr(w3.eth, "accounts") and w3.eth.accounts else None
    except Exception:
        accounts0 = None

    latest_block = w3.eth.block_number

    print("=== debug_env.py ===")
    print(f"RPC_URL={rpc_url}")
    print(f"chain_id={chain_id}")
    print(f"net_version={net_version}")
    print(f"latest_block={latest_block}")
    print(f"accounts[0]={accounts0}")
    print(f"artifact={BUILD_CONTRACTS_DIR / f'{CONTRACT_NAME}.json'}")
    print(f"resolved_contract_address={contract_address}")
    print(f"deployed_bytecode_length={len(bytecode) if bytecode is not None else None}")

    # Dump a small subset of networks keys for clarity
    networks = artifact.get("networks") or {}
    print(f"artifact_network_keys={sorted(list(networks.keys()))}")


if __name__ == "__main__":
    main()

