#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import secrets
import sys

try:
    from eth_keys import keys
    from web3 import Web3
except ImportError as exc:
    raise SystemExit("Install eth-keys and web3 (pip install eth-keys web3)") from exc

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data: bytes) -> str:
    num = int.from_bytes(data, "big")
    encoded = ""
    while num > 0:
        num, rem = divmod(num, 58)
        encoded = BASE58_ALPHABET[rem] + encoded
    leading = 0
    for byte in data:
        if byte == 0:
            leading += 1
        else:
            break
    return "1" * leading + encoded


def h160_to_ss58(address: str, ss58_format: int = 42) -> str:
    addr_bytes = bytes.fromhex(address[2:])
    prefixed = b"evm:" + addr_bytes
    public_key = hashlib.blake2b(prefixed, digest_size=32).digest()
    if ss58_format < 64:
        prefix = bytes([ss58_format])
    else:
        ss58_format |= 0b01000000
        prefix = bytes([ss58_format & 0xFF, (ss58_format >> 8) & 0xFF])
    payload = prefix + public_key
    checksum = hashlib.blake2b(b"SS58PRE" + payload, digest_size=64).digest()[:2]
    return b58encode(payload + checksum)


def generate_keypair():
    priv_bytes = secrets.token_bytes(32)
    private_key = keys.PrivateKey(priv_bytes)
    public_key = private_key.public_key
    address_bytes = public_key.to_canonical_address()
    checksum_address = Web3.to_checksum_address("0x" + address_bytes.hex())
    return {
        "private_key": "0x" + private_key.to_hex(),
        "public_key": "0x" + public_key.to_hex(),
        "address": checksum_address,
        "ss58": h160_to_ss58(checksum_address),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate a new H160 EVM keypair.")
    parser.add_argument(
        "--output",
        help="Optional path to write the keypair JSON (defaults to stdout).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    args = parser.parse_args()

    try:
        import eth_keys  # noqa: F401  # ensure dependency is installed
    except ImportError as exc:
        raise SystemExit("Install eth-keys (pip install eth-keys) to use this helper") from exc

    keypair = generate_keypair()

    if args.output:
        path = os.path.expanduser(args.output)
        if os.path.exists(path) and not args.force:
            raise SystemExit(f"{path} already exists. Use --force to overwrite.")
        with open(path, "w") as f:
            json.dump(keypair, f, indent=2)
        print(f"Wrote keypair to {path}")
    else:
        print(json.dumps(keypair, indent=2))


if __name__ == "__main__":
    main()
