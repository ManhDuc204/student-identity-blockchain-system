import os

from web3 import Web3


# NOTE:
# contract address + ABI are now loaded dynamically from Truffle artifact
# by blockchain/connect_blockchain.py (based on runtime chain_id).

# =========================
# DEFAULT CONFIG (GANACHE SAFE)
# =========================
DEFAULT_RPC_URL = "http://127.0.0.1:7545"
DEFAULT_GAS = 600000


# =========================
# CHAIN CONFIG
# =========================
def get_chain_config():
    pk = os.environ.get("PRIVATE_KEY")
    account_address = os.environ.get("ACCOUNT_ADDRESS")

    # If ACCOUNT_ADDRESS isn't provided, try to infer from the private key.
    if not account_address and pk:
        try:
            tmp_w3 = None  # only used for account derivation
            acct = Web3().eth.account.from_key(pk)
            account_address = acct.address
        except Exception:
            account_address = None

    return {
        "rpc_url": os.environ.get("RPC_URL", DEFAULT_RPC_URL),
        "private_key": pk,
        "account_address": account_address,
        "gas": int(os.environ.get("TX_GAS", DEFAULT_GAS)),
        "gas_price_wei": int(os.environ.get("TX_GAS_PRICE_WEI", "20000000000"))
        if os.environ.get("TX_GAS_PRICE_WEI") else None,
    }


