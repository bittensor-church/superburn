#!/bin/bash

# PRIVATE_KEY needs to be exported with 0x-prefixed private key

export BITTENSOR_RPC_URL="https://test.chain.opentensor.ai"
TARGET=${1:-SuperBurn}

case "$TARGET" in
  SuperBurn)
    SOL="Deploy.s.sol:Deploy"
    ;;
  *)
    echo "Unknown target: $TARGET" >&2
    exit 1
    ;;
esac

forge script script/$SOL --rpc-url $BITTENSOR_RPC_URL --broadcast --chain-id 945
