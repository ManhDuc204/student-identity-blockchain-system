import json
import sys

from web3 import Web3

from blockchain.connect_blockchain import get_web3, get_contract



def main():
    w3 = get_web3()

    print("=== Web3 connection ===")
    print("connected:", w3.is_connected())
    print("chain_id:", w3.eth.chain_id)
    print("block_number:", w3.eth.block_number)
    print("account0:", w3.eth.accounts[0] if w3.eth.accounts else None)

    contract, _ = get_contract()

    addr = contract.address
    print("\n=== Contract ===")
    print("address:", addr)

    # Pick a test student_id
    student_id = sys.argv[1] if len(sys.argv) > 1 else "student_001"

    print("\n=== Call getStudentHash ===")
    try:
        value = contract.functions.getStudentHash(student_id).call()
        # bytes32 as hex string
        print("student_id:", student_id)
        if isinstance(value, (bytes, bytearray)):
            print("result (bytes):", value)
            print("result (hex):", Web3.to_hex(value))
        else:
            print("result:", value)
    except Exception as e:
        print("Call failed:", repr(e))
        # best effort: print bytecode existence
        code = w3.eth.get_code(addr)
        print("deployed_bytecode_present:", bool(code) and code not in (b"", b"0x") )
        raise


if __name__ == "__main__":
    main()

