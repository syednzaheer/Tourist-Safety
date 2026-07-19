"""
Thin wrapper around web3.py for talking to the deployed TouristID
contract. Same pattern as the Twilio integration in routers/sos.py:
fully optional, and everything else in the app works fine without it
configured - the JWT is still the fast local check either way, this
just adds a chain-verifiable second source of truth for cross-border
checkpoints that don't want to trust one state's API directly.

Configure via env vars:
    CHAIN_RPC_URL       - e.g. an Alchemy/Infura Sepolia or Polygon Amoy testnet URL
    CHAIN_PRIVATE_KEY   - the backend's wallet private key (issuer/owner of the contract)
    CHAIN_CONTRACT_ADDRESS - address TouristID.sol was deployed to (see deploy.py)

Without all three set, is_configured() returns False and every call
below is a no-op that returns None - callers are expected to check
is_configured() and fall back to JWT-only, same as SMS falls back to
"simulated".
"""
import json
import os
from pathlib import Path

RPC_URL = os.environ.get("CHAIN_RPC_URL")
PRIVATE_KEY = os.environ.get("CHAIN_PRIVATE_KEY")
CONTRACT_ADDRESS = os.environ.get("CHAIN_CONTRACT_ADDRESS")

_ABI_PATH = Path(__file__).parent / "abi.json"

_w3 = None
_contract = None
_account = None


def is_configured() -> bool:
    return bool(RPC_URL and PRIVATE_KEY and CONTRACT_ADDRESS)


def _get_client():
    """Lazily connects on first real use, not at import time - importing
    this module shouldn't fail just because no one's set the env vars yet."""
    global _w3, _contract, _account

    if not is_configured():
        return None, None, None

    if _w3 is not None:
        return _w3, _contract, _account

    from web3 import Web3  # imported lazily; web3 is an optional dependency

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = w3.eth.account.from_key(PRIVATE_KEY)
    abi = json.loads(_ABI_PATH.read_text())
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)

    _w3, _contract, _account = w3, contract, account
    return w3, contract, account


def _tourist_id_to_bytes32(tourist_id: str):
    from web3 import Web3
    return Web3.keccak(text=tourist_id)


def _raw_bytes(signed_tx):
    """web3.py renamed SignedTransaction.rawTransaction to raw_transaction
    somewhere around v7. Handle either so this doesn't break depending on
    which version ends up installed."""
    return getattr(signed_tx, "raw_transaction", None) or signed_tx.rawTransaction


def _send(w3, account, tx):
    tx.setdefault("gas", 300_000)
    tx.setdefault("gasPrice", w3.eth.gas_price)
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(_raw_bytes(signed))
    w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex()


def issue_onchain(tourist_id: str, trip_start_ts: int, trip_end_ts: int, data_hash_hex: str) -> str | None:
    """Mints the identity on-chain. Returns the tx hash (hex string), or
    None if blockchain isn't configured - callers should treat None as
    "skipped, not failed" and keep going with the JWT path."""
    w3, contract, account = _get_client()
    if w3 is None:
        return None

    touristid_bytes32 = _tourist_id_to_bytes32(tourist_id)
    data_hash_bytes32 = bytes.fromhex(data_hash_hex.removeprefix("0x"))

    tx = contract.functions.issueIdentity(
        touristid_bytes32, trip_start_ts, trip_end_ts, data_hash_bytes32
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
    })
    return _send(w3, account, tx)


def is_valid_onchain(tourist_id: str) -> bool | None:
    """Returns True/False from the chain, or None if not configured -
    None is not the same as False, callers should distinguish "couldn't
    check" from "checked and it's invalid"."""
    w3, contract, _ = _get_client()
    if w3 is None:
        return None
    return contract.functions.isValid(_tourist_id_to_bytes32(tourist_id)).call()


def revoke_onchain(tourist_id: str) -> str | None:
    w3, contract, account = _get_client()
    if w3 is None:
        return None

    tx = contract.functions.revokeIdentity(
        _tourist_id_to_bytes32(tourist_id)
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
    })
    return _send(w3, account, tx)
