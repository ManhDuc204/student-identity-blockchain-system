# TODO - Student Flask Blockchain (Ganache/LiteLLM stable pipeline)

## Step 1: Refactor blockchain/connect_blockchain.py (complete)
- [ ] Restructure module into clear sections (web3 connection, artifact loading, contract resolution, validations, tx senders, reads)
- [ ] Add strict runtime artifact network resolution by chain_id
- [ ] Add deployed bytecode verification + ABI validation for addStudent/getStudentHash
- [x] Implement local (Ganache) add/delete tx flow WITHOUT fn.transact()
  - [x] nonce = w3.eth.get_transaction_count(account, "pending")
  - [x] build_transaction + estimate_gas happens inside build_eip1559_tx/build_legacy_tx
  - [x] fee config (EIP-1559 when supported; else legacy gasPrice)
  - [x] send_transaction() and wait_for_transaction_receipt()
  - [x] receipt.status check + detailed logging
- [x] Implement production tx flow consistently with same tx builder (signed raw tx ok)
- [x] Add post-add verification by calling getStudentHash(student_id) and comparing with local data_hash
- [x] Add on-chain mismatch logs/warnings
- [ ] Add protections: stale artifact/Ganache reset, nonce too low, duplicate student_id handling (if contract reverts), placeholder/invalid env
- [x] Add debug logs: chain_id, selected account, tx mode, nonce(pending), base fee, priority/max fee, deployed contract address, bytecode length


## Step 2: Create repair_artifact.py
- [x] Script runs compile + migrate --reset --verbose (as requested)
- [x] Validates resulting build/contracts/StudentIdentity.json contains networks[chain_id]
- [x] Validates deployed code length at resolved address
- [x] Prints clear report

## Step 3: Create debug_env.py
- [ ] Connect to Ganache RPC, print chain_id/net_version/accounts[0], block number
- [ ] Validate artifact + deployed bytecode length for resolved contract address
- [ ] Print detailed env diagnostics

## Step 4: Verify add_student + verify flows
- [ ] Run: npx truffle compile --all
- [ ] Run: npx truffle migrate --reset --verbose
- [ ] Run: python repair_artifact.py (optional if steps 1/2 already sufficient)
- [ ] Run: python debug_env.py
- [ ] Start Flask app; add student multiple times; check tx logs + DB updates
- [ ] Use /verify route; ensure on-chain hash matches
- [ ] Restart Ganache and confirm mismatch detection message is clear


