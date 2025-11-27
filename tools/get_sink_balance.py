#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys

try:
    from web3 import Web3
except ImportError as exc:
    raise SystemExit("Install web3 python package to use this helper") from exc


def load_sink_abi() -> list:
    artifact = pathlib.Path(__file__).parent.parent / "out" / "SuperBurn.sol" / "SuperBurn.json"
    try:
        return json.loads(artifact.read_text())["abi"]
    except FileNotFoundError as exc:
        raise SystemExit(f"Sink artifact not found at {artifact}") from exc


def resolve_rpc_url(args: argparse.Namespace) -> str:
    if args.rpc_url:
        return args.rpc_url
    try:
        import bittensor.utils
    except ImportError as exc:
        raise SystemExit(
            "Install bittensor or pass --rpc-url to specify the endpoint explicitly"
        ) from exc
    _, network_url = bittensor.utils.determine_chain_endpoint_and_network(args.network)
    return network_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Read Sink.getBalance() from a deployed contract")
    parser.add_argument("contract", help="Deployed Sink contract address (0x...)")
    parser.add_argument(
        "--rpc-url",
        help="HTTP(s) RPC endpoint. Required when bittensor is not installed",
    )
    parser.add_argument(
        "--network",
        default="finney",
        help="Bittensor network key understood by bittensor.utils (default: finney)",
    )
    args = parser.parse_args()

    rpc_url = resolve_rpc_url(args)
    if rpc_url.startswith("ws"):
        websocket_provider = (
            getattr(Web3, "WebsocketProvider", None)
            or getattr(Web3, "WebSocketProvider", None)
            or getattr(Web3, "LegacyWebSocketProvider", None)
        )
        if websocket_provider is None:
            raise SystemExit("web3 installation does not expose a WebSocket provider; try an HTTP RPC URL")
        provider = websocket_provider(rpc_url)  # type: ignore[call-arg]
    else:
        provider = Web3.HTTPProvider(rpc_url)

    w3 = Web3(provider)
    if not w3.is_connected():
        raise SystemExit(f"Failed to connect to RPC at {rpc_url}")

    abi = load_sink_abi()
    contract = w3.eth.contract(address=Web3.to_checksum_address(args.contract), abi=abi)

    balance_wei = contract.functions.getBalance().call()
    balance_tao = w3.from_wei(balance_wei, "ether")

    print(f"Sink balance: {balance_tao} TAO")
    print(f"Sink balance (wei): {balance_wei}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
