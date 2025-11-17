#!/usr/bin/env python3
"""
Invoke Sink.registerNeuron() from the command line.

"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys

try:
    from web3 import Web3
    from web3.exceptions import ContractLogicError
except ImportError as exc:
    raise SystemExit("Install web3 (pip install web3) to use this helper") from exc


ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT_DIR / "out" / "Sink.sol" / "Sink.json"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call Sink.registerNeuron via web3.")
    parser.add_argument("contract", help="Sink contract address (0x...)")
    parser.add_argument("--netuid", required=True, type=int, help="Subnet netuid to register in (uint16)")
    parser.add_argument(
        "--hotkey-ss58",
        required=True,
        help="SS58-formatted hotkey; converted to bytes32 automatically.",
    )
    value = parser.add_mutually_exclusive_group(required=True)
    value.add_argument("--value-tao", type=float, help="Amount of TAO to burn (float)")
    value.add_argument("--value-wei", type=int, help="Amount in wei to burn")
    parser.add_argument(
        "--rpc-url",
        help="RPC endpoint (HTTP or WS). If omitted, --network + bittensor must be available.",
    )
    parser.add_argument(
        "--network",
        default="finney",
        help="Bittensor network key understood by bittensor.utils (default: finney).",
    )
    parser.add_argument(
        "--gas-limit",
        type=int,
        help="Optional explicit gas limit. Otherwise an estimate is used.",
    )
    parser.add_argument(
        "--gas-price",
        type=int,
        help="Gas price in wei. Defaults to w3.eth.gas_price.",
    )
    parser.add_argument(
        "--wait/--no-wait",
        dest="wait",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Wait for transaction receipt (default: True).",
    )
    return parser.parse_args()


def load_abi() -> list:
    try:
        return json.loads(ARTIFACT_PATH.read_text())["abi"]
    except FileNotFoundError as exc:
        raise SystemExit(f"Sink artifact missing at {ARTIFACT_PATH}. Run `forge build`.") from exc


def b58decode(data: str) -> bytes:
    num = 0
    for char in data:
        num *= 58
        if char not in BASE58_ALPHABET:
            raise ValueError(f"Character {char} is not valid base58")
        num += BASE58_ALPHABET.index(char)
    combined = num.to_bytes((num.bit_length() + 7) // 8, byteorder="big")
    leading = 0
    for char in data:
        if char == "1":
            leading += 1
        else:
            break
    return b"\x00" * leading + combined


def decode_ss58_hotkey(ss58: str) -> bytes:
    decoded = b58decode(ss58)
    if len(decoded) < 34:
        raise SystemExit("SS58 address too short")
    format_byte = decoded[0]
    if format_byte >= 64:
        raise SystemExit("Unsupported SS58 format (>=64)")
    pubkey = decoded[1:-2]
    checksum = decoded[-2:]
    expected = hashlib.blake2b(b"SS58PRE" + decoded[:-2], digest_size=64).digest()[:2]
    if checksum != expected:
        raise SystemExit("Invalid SS58 checksum")
    if len(pubkey) != 32:
        raise SystemExit(f"Expected 32-byte hotkey, got {len(pubkey)} bytes")
    print(f"SS58 hotkey decoded to bytes32: 0x{pubkey.hex()}")
    return pubkey


def resolve_rpc_url(args: argparse.Namespace) -> str:
    if args.rpc_url:
        return args.rpc_url
    try:
        import bittensor.utils
    except ImportError as exc:
        raise SystemExit(
            "Install bittensor or provide --rpc-url to connect to a node."
        ) from exc
    _, url = bittensor.utils.determine_chain_endpoint_and_network(args.network)
    return url


def make_provider(rpc_url: str):
    if rpc_url.startswith("ws"):
        candidate = (
            getattr(Web3, "WebsocketProvider", None)
            or getattr(Web3, "WebSocketProvider", None)
            or getattr(Web3, "LegacyWebSocketProvider", None)
        )
        if candidate is None:
            raise SystemExit("web3 package lacks WebSocket provider; use an HTTP RPC URL.")
        return candidate(rpc_url)
    return Web3.HTTPProvider(rpc_url)


def resolve_hotkey(args: argparse.Namespace) -> bytes:
    return decode_ss58_hotkey(args.hotkey_ss58)


def resolve_private_key() -> str:
    key = os.getenv("PRIVATE_KEY")
    if not key:
        raise SystemExit("Set PRIVATE_KEY environment variable to sign the transaction.")
    key = key.strip()
    return key if key.startswith("0x") else "0x" + key


def resolve_value_wei(args: argparse.Namespace, w3: Web3) -> int:
    if args.value_wei is not None:
        return args.value_wei
    assert args.value_tao is not None
    return int(args.value_tao * 1_000_000_000)

def build_and_send_transaction(
    w3: Web3,
    function_call,
    account,
    gas_limit: int,
    gas_price: int,
    value: int,
):
    """Build, sign, and submit the registerNeuron transaction."""
    tx = function_call.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": gas_limit,
            "gasPrice": gas_price,
            "chainId": w3.eth.chain_id,
            "value": value,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Transaction sent: {tx_hash.hex()}", file=sys.stderr)
    return tx_hash


def wait_for_receipt(w3: Web3, tx_hash, timeout=300, poll_latency=2):
    return w3.eth.wait_for_transaction_receipt(tx_hash, timeout, poll_latency)


def explain_revert(w3: Web3, tx_hash, block_number: int) -> str:
    tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else tx_hash
    try:
        tx = w3.eth.get_transaction(tx_hash_hex)
        w3.eth.call(
            {
                "to": tx["to"],
                "from": tx["from"],
                "data": tx["input"],
                "value": tx["value"],
            },
            block_identifier=block_number,
        )
        return "Call succeeded on replay; no revert reason available."
    except ContractLogicError as exc:
        message = str(exc)
        match = re.search(r"0x[a-fA-F0-9]{8,}", message)
        if match:
            selector = match.group(0)
            if selector == "0x00000000":
                # Attempt to parse Subtensor's DispatchError string
                detail = re.search(r"execution reverted: (.+)", message)
                return detail.group(1) if detail else f"{selector} ({message})"
            return f"{selector} ({message})"
        return f"ContractLogicError: {message}"
    except Exception as exc:  # pragma: no cover - best-effort logging
        return f"Failed to replay transaction: {exc}"

def main() -> None:
    args = parse_args()
    rpc_url = resolve_rpc_url(args)
    provider = make_provider(rpc_url)
    w3 = Web3(provider)
    if not w3.is_connected():
        raise SystemExit(f"Failed to connect to {rpc_url}")

    abi = load_abi()
    contract = w3.eth.contract(address=Web3.to_checksum_address(args.contract), abi=abi)
    private_key = resolve_private_key()
    account = w3.eth.account.from_key(private_key)

    hotkey_bytes = resolve_hotkey(args)
    value_wei = resolve_value_wei(args, w3)
    function = contract.functions.registerNeuron(args.netuid, hotkey_bytes)

    gas_limit = args.gas_limit or 200000
    gas_price = args.gas_price or w3.eth.gas_price

    tx_hash = build_and_send_transaction(
        w3=w3,
        function_call=function,
        account=account,
        gas_limit=gas_limit,
        gas_price=gas_price,
        value=value_wei,
    )
    print(f"Sent registerNeuron tx: {tx_hash.hex()}")

    if not args.wait:
        return

    receipt = wait_for_receipt(w3, tx_hash)
    status = "SUCCESS" if receipt["status"] == 1 else "FAILED"
    print(f"Receipt status: {status}")
    print(f"Gas used: {receipt['gasUsed']}")
    print(f"Block: {receipt['blockNumber']}")

    if receipt["status"] != 1:
        reason = explain_revert(w3, tx_hash, receipt["blockNumber"])
        print(f"Revert reason: {reason}")
    print(f"{receipt}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
