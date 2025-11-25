#!/usr/bin/env python3
"""
CLI tool to fetch and display stake info for a given Coldkey.
Uses the shared utils.staking_manager logic.
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to sys.path to allow imports from utils package
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# Import shared logic
try:
    from utils.staking_manager import fetch_validator_stakes
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import utils. Ensure 'tools/utils/__init__.py' exists. {e}", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Fetch stake info for a Coldkey.")
    parser.add_argument("--coldkey", required=True, help="Coldkey SS58 address")
    parser.add_argument("--netuid", type=int, required=True, help="Network UID (e.g., 285)")
    parser.add_argument("--network", default="test", help="Bittensor network name (test, finney). Default: test")

    # Optional compatibility arg (ignored)
    parser.add_argument("--rpc-url", help="Ignored (for compatibility only)")

    args = parser.parse_args()

    try:
        hotkeys_bytes32, amounts_tao = fetch_validator_stakes(
            coldkey_ss58=args.coldkey,
            netuid=args.netuid,
            network=args.network
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not hotkeys_bytes32:
        print(f"No stake found for {args.coldkey} on NetUID {args.netuid}.")
        sys.exit(0)

    print("-" * 50)
    print(f"FOUND STAKE DATA (NetUID: {args.netuid}, Network: {args.network})")
    print("-" * 50)

    for i, hk in enumerate(hotkeys_bytes32):
        # Convert bytes32 to hex string for display
        hk_hex = "0x" + hk.hex()
        amount = amounts_tao[i]
        print(f"Validator {i+1}:")
        print(f"  Hotkey (Pub32): {hk_hex}")
        print(f"  Stake (TAO):    {amount}")
        print("-" * 50)

    print(f"Total Validators: {len(hotkeys_bytes32)}")
    print(f"Total Stake:      {sum(amounts_tao)} TAO")

if __name__ == "__main__":
    main()