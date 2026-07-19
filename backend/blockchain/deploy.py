"""
Compiles and deploys TouristID.sol to whatever RPC_URL points at -
a local Hardhat/Anvil node for testing, or a real testnet (Sepolia,
Polygon Amoy) for a demo that judges can independently verify on a
block explorer.

Needs network access to (a) download the solc compiler on first run and
(b) actually broadcast the deploy transaction, so this won't run in a
sandboxed/offline environment - run it from your own machine.

Usage:
    pip install py-solc-x
    export CHAIN_RPC_URL=...
    export CHAIN_PRIVATE_KEY=...      # needs testnet funds - use a faucet, never a real wallet
    python3 deploy.py

Prints the deployed contract address - put that in CHAIN_CONTRACT_ADDRESS
for the backend to use.
"""
import json
import os
from pathlib import Path

from solcx import compile_source, install_solc, set_solc_version
from web3 import Web3

SOLC_VERSION = "0.8.20"
CONTRACT_PATH = Path(__file__).parent / "contracts" / "TouristID.sol"


def compile_contract():
    install_solc(SOLC_VERSION)
    set_solc_version(SOLC_VERSION)

    source = CONTRACT_PATH.read_text()
    compiled = compile_source(source, output_values=["abi", "bin"])
    contract_id, contract_interface = compiled.popitem()
    return contract_interface["abi"], contract_interface["bin"]


def main():
    rpc_url = os.environ["CHAIN_RPC_URL"]
    private_key = os.environ["CHAIN_PRIVATE_KEY"]

    abi, bytecode = compile_contract()

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = w3.eth.account.from_key(private_key)

    TouristID = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = TouristID.constructor().build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 2_000_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = account.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"Deployed TouristID at: {receipt.contractAddress}")
    print(f"Tx hash: {tx_hash.hex()}")

    # write the ABI out too, in case the contract shape changes and the
    # hand-written abi.json needs regenerating
    abi_out = Path(__file__).parent / "abi.deployed.json"
    abi_out.write_text(json.dumps(abi, indent=2))
    print(f"ABI written to {abi_out}")


if __name__ == "__main__":
    main()
