import os

from blockchain.connect_blockchain import get_web3, get_contract
from blockchain.connect_blockchain import send_add_student_tx


def main():
    # Minimal offline check: just send a transaction.
    # Requires env: RPC_URL, PRIVATE_KEY (and optionally ACCOUNT_ADDRESS)

    # Make student_id unique per run to avoid revert "studentId already exists".
    # You can still override via TEST_STUDENT_ID env var if needed.
    base_student_id = os.environ.get("TEST_STUDENT_ID", "TEST001")
    if base_student_id.startswith("SV001_") or "_" in base_student_id:
        # Keep as-is if user already uses unique ids (heuristic).
        student_id = base_student_id
    else:
        import datetime

        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        student_id = f"{base_student_id}_{ts}"
    # 32-byte dummy hash (bytes32) as hex: 64 hex chars
    data_hash_hex = os.environ.get(
        "TEST_DATA_HASH_HEX",
        "00000000000000000000000000000000000000000000000000000000deadbeef"[-64:],
    )

    w3 = get_web3()
    contract, _ = get_contract()

    print("chain_id", w3.eth.chain_id)
    print("contract", contract.address)

    receipt = send_add_student_tx(student_id, data_hash_hex)
    print("receipt status", receipt.status)
    print("tx hash", receipt.transactionHash.hex())
    print("block", receipt.blockNumber)


if __name__ == "__main__":
    main()

