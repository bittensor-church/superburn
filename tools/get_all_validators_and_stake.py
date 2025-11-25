import json
import subprocess
import sys
import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Fetch stake info and optionally unstake/burn.")
parser.add_argument("--coldkey", required=True, help="Coldkey SS58 address")
parser.add_argument("--hotkeys", required=True, nargs="+", help="List of hotkey SS58 addresses")
parser.add_argument("--netuid", type=int, required=True, help="Network UID")
parser.add_argument("--rpc-url", required=True, help="RPC URL")
parser.add_argument("--private-key", required=True, help="Private key for signing transactions")
parser.add_argument("--unstake-burn", action="store_true", help="If set, perform unstake and burn")
args = parser.parse_args()

COLDKEY = args.coldkey
HOTKEYS = args.hotkeys
NETUID = args.netuid
RPC_URL = args.rpc_url
PRIVATE_KEY = args.private_key

# Fetch stake information
cmd = [
    "btcli", "stake", "list",
    "--network", "test",
    "--ss58", COLDKEY,
    "--json-out"
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("Error fetching stake info:", result.stderr)
    sys.exit(1)

data = json.loads(result.stdout)

# Calculate total stake for each hotkey
amounts = []
for hk in HOTKEYS:
    stake_entries = data.get("stake_info", {}).get(hk, [])
    total_value = sum(entry.get("stake_value", 0) for entry in stake_entries)
    amounts.append(total_value)

print(f"Hotkeys: {HOTKEYS}")
print(f"Amounts to unstake: {amounts}")

# if args.unstake-burn:
#     cmd_burn = [
#                    "python3", "tools/unstake_and_burn_batch.py",
#                    COLDKEY,
#                    "--hotkeys"
#                ] + HOTKEYS + [
#                    "--amounts"
#                ] + [str(a) for a in amounts] + [
#                    "--netuid", str(NETUID),
#                    "--rpc-url", RPC_URL,
#                    "--private-key", PRIVATE_KEY
#                ]
#
#     subprocess.run(cmd_burn)
