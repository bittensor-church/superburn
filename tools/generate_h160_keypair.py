#!/usr/bin/env python3
"""
Generates a new H160 EVM keypair and calculates its SS58 equivalent.
Uses the shared address_converter utility.
"""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

# Add the tools directory to sys.path to allow imports from utils
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

try:
    from eth_keys import keys
    from web3 import Web3
    # Import the shared logic
    from utils.address_converter import h160_to_ss58
except ImportError as exc:
    print("CRITICAL ERROR: Missing dependencies.", file=sys.stderr)
    print("Please run: pip install eth-keys web3", file=sys.stderr)
    # Note: utils module import error will also be caught here if structure is wrong
    raise SystemExit(1) from exc


def generate_keypair():
    """
    Generates a random private key, derives the Ethereum address,
    and calculates the Bittensor SS58 representation.
    """
    # 1. Generate random 32 bytes for private key
    priv_bytes = secrets.token_bytes(32)
    private_key = keys.PrivateKey(priv_bytes)

    # 2. Derive public key and EVM address
    public_key = private_key.public_key
    address_bytes = public_key.to_canonical_address()
    checksum_address = Web3.to_checksum_address("0x" + address_bytes.hex())

    # 3. Derive SS58 address using shared utility
    # This ensures consistency across the entire project
    ss58_address = h160_to_ss58(checksum_address)

    return {
        "private_key": private_key.to_hex(),
        "public_key": public_key.to_hex(),
        "address": checksum_address,     # EVM Address (H160)
        "ss58": ss58_address,            # Bittensor Address (Coldkey)
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

    # Generate the keys
    keypair = generate_keypair()

    # Output handling
    if args.output:
        path = os.path.expanduser(args.output)
        if os.path.exists(path) and not args.force:
            print(f"Error: {path} already exists. Use --force to overwrite.", file=sys.stderr)
            sys.exit(1)

        with open(path, "w") as f:
            json.dump(keypair, f, indent=2)
        print(f"Success: Wrote keypair to {path}")
    else:
        print(json.dumps(keypair, indent=2))


if __name__ == "__main__":
    main()
