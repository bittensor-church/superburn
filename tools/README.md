# Tools
- `generate_h160_keypair.py` – Generates a random EVM keypair and prints/writes the private key, public key, H160 address, and SS58 form.
- `h160_to_ss58.py` – Converts an EVM H160 address (0x…) into SS58 format.
- `register_neuron_minimal.py` – Minimal CLI that pre-funds the `RegisterOnly` helper via the balance transfer precompile (auto-computes the contract SS58 mirror from its H160), then calls `burnedRegisterNeuron` with a provided hotkey bytes32 and configurable burn amount; any leftover balance is refunded to the caller (HTTP RPC).
- `set_weights.py` – Sets validator weights on a Bittensor subnet by UID or hotkey with optional normalization, dry-run, and network/endpoint selection.

## not maintained
- `get_sink_balance.py` – Reads `Sink.getBalance()` for a deployed Sink contract using the compiled ABI and a provided RPC endpoint
- `register_neuron.py` – Full-featured helper to call `Sink.registerNeuron`, decoding an SS58 hotkey, building/sending the transaction, and reporting the receipt or revert reason.
