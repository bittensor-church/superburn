# Sink - Bittensor Burn Contract

A minimal, trustless smart contract that permanently burns staked TAO tokens on the Bittensor network using precompiled contracts. **No owners, no admins, fully autonomous.**

## Overview

The Sink contract provides a simple, trustless mechanism to burn staked TAO tokens on Bittensor. Anyone can call `burnAll()` to unstake and burn the contract's balance and receive gas reimbursement for their transaction costs.

**Process:** Receive staked TAO → Unstake via precompile → Burn liquid TAO → Reimburse caller

## Design Principles

- 🔓 **No administrative control** - No owners, no pause, no upgrades
- 🤖 **Fully autonomous** - Anyone can trigger burns
- 💰 **Incentivized execution** - Callers are reimbursed for gas costs
- 🎯 **Minimal attack surface** - Single public function, no state variables
- 🔒 **Immutable** - Once deployed, behavior cannot be changed

## Features

- **burnAll()**: Unstakes and burns all staked tokens held by the contract
- **Two-step process**: Unstake staked TAO → Burn liquid TAO
- **Gas Reimbursement**: Callers receive gas cost reimbursement
- **Stateless**: No state variables (except constants)
- **No receive() function**: Tokens must be force-sent (prevents accidental deposits)
- **Event Logging**: Track all unstakes and burns with detailed events
- **Neuron Registration Helpers**:
  - `Sink.registerNeuron` forwards `burnedRegister` calls (and funds) to the neuron precompile so the contract can self-register as a miner.
  - `RegisterOnly.sol` exposes a standalone `burnedRegisterNeuron` helper that takes an explicit burn amount, forwards only that value from the contract balance to the precompile, and refunds the remaining balance back to the caller.

## Contract Architecture

```solidity
contract Sink {
    // Constants
    address private constant UNSTAKE_PRECOMPILE = 0x0000000000000000000000000000000000000801;
    address private constant NEURON_PRECOMPILE = 0x0000000000000000000000000000000000000804;
    uint256 private constant REIMBURSEMENT_BUFFER = 90000; // Gas units

    // Single public function
    function burnAll() external returns (bool);

    // View functions
    function getBalance() external view returns (uint256); // Returns staked balance
    function estimateReimbursement() external view returns (uint256);

    // Miner registration helper
    function registerNeuron(uint16 netuid, bytes32 hotkey) external payable returns (bool);
}
```

### Key Design Decisions

**No receive() Function**
- Prevents accidental deposits
- Simpler interface (single entry point)
- Tokens must be force-sent via selfdestruct or coinbase

**Stateless Design**
- No storage variables (lower gas costs)
- No state to corrupt
- Fully deterministic behavior

**Gas Reimbursement**
- Incentivizes anyone to call burnAll()
- Formula: `gasReimbursement = (gasUsed + BUFFER) * tx.gasprice`
- Buffer calibrated to ~100,000 gas units (covers unstake + burn operations)

### Neuron Registration Utilities

- `deploy-testnet.sh` accepts a target parameter. Run `./deploy-testnet.sh Sink` (default) to deploy the burn contract or `./deploy-testnet.sh RegisterOnly` to deploy the minimal `RegisterOnly.sol` helper.
- `tools/register_neuron.py` is the fully featured helper that decodes SS58 hotkeys to bytes32, loads the Sink ABI, and signs transactions using `PRIVATE_KEY`.
- `tools/register_neuron_minimal.py` is a stripped-down variant for the `RegisterOnly` contract. It pre-funds the helper contract via the balance-transfer precompile (auto-computing the contract’s SS58 mirror from its H160), then calls `burnedRegisterNeuron` with a specified burn amount (defaults to the prefund), and the contract refunds any leftover balance. It expects a raw `--hotkey-bytes32`, always estimates gas (falling back to 200,000 if estimation fails), and prints transaction status plus the emitted RegisterAttempt event.

## Installation

### Prerequisites

- [Foundry](https://book.getfoundry.sh/getting-started/installation)

### Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd sink

# Install dependencies
forge install

# Build the contract
forge build

# Run tests
forge test

# Run tests with gas reporting
forge test --gas-report
```

## Testing

The project includes **23 comprehensive tests** covering:

- ✅ Unstaking functionality
- ✅ Burning functionality
- ✅ Gas reimbursement calculations
- ✅ Error conditions (insufficient balance, unstake failure, burn failure)
- ✅ No receive/fallback functions (rejects direct sends)
- ✅ Forced send mechanisms
- ✅ Stateless behavior verification
- ✅ Fuzz testing with random amounts and gas prices
- ✅ Integration workflows
- ✅ Edge cases (zero balance, very small/large balances)

```bash
# Run all tests
forge test

# Run specific test
forge test --match-test test_BurnAll_Success

# Run with coverage
forge coverage

# Run with gas snapshot
forge snapshot

# Run with verbosity
forge test -vvv
```

### Test Results

All 22 tests passing:
- Unstaking: ✅
- Burning: ✅
- Gas reimbursement: ✅
- Error handling: ✅
- No receive/fallback: ✅
- Fuzz testing: ✅
- Integration tests: ✅

## Deployment

### Environment Setup

Create a `.env` file:

```bash
PRIVATE_KEY=<your-private-key>
BITTENSOR_RPC_URL=<bittensor-rpc-endpoint>
BITTENSOR_TESTNET_RPC_URL=<testnet-rpc-endpoint>
```

### Deploy to Bittensor

```bash
# Deploy to Bittensor testnet
forge script script/Deploy.s.sol:Deploy \
    --rpc-url $BITTENSOR_TESTNET_RPC_URL \
    --broadcast

# Deploy to Bittensor mainnet (after testing!)
forge script script/Deploy.s.sol:Deploy \
    --rpc-url $BITTENSOR_RPC_URL \
    --broadcast \
    --verify
```

### Deployment Checklist

Before deploying to mainnet:

- [ ] Verify the unstake precompile address (`0x0000000000000000000000000000000000000801`)
- [ ] Test on Bittensor testnet
- [ ] Verify unstake precompile functionality works as expected
- [ ] Verify tokens sent to address(0) are permanently burned
- [ ] Test gas reimbursement accuracy
- [ ] Review all test results
- [ ] Audit the contract (recommended)
- [ ] Test forced send mechanisms

## Usage

### Funding the Contract

Since the contract has no `receive()` function, tokens must be sent via:

1. **Force send** (selfdestruct from another contract)
2. **Coinbase transaction** (if contract address is miner/validator)
3. **Pre-funding** (send funds before deployment to calculated address)

Example force send:
```solidity
contract ForceSender {
    function sendToSink(address payable sink) external payable {
        selfdestruct(sink);
    }
}
```

### Triggering Burns

Anyone can call `burnAll()` to burn the contract's balance and receive gas reimbursement:

```bash
# Burn all tokens (and get reimbursed)
cast send <SINK_CONTRACT_ADDRESS> \
    "burnAll()" \
    --rpc-url $BITTENSOR_RPC_URL \
    --private-key $PRIVATE_KEY
```

### Querying Contract State

```bash
# Get current balance
cast call <SINK_CONTRACT_ADDRESS> "getBalance()" --rpc-url $BITTENSOR_RPC_URL

# Estimate gas reimbursement
cast call <SINK_CONTRACT_ADDRESS> "estimateReimbursement()" --rpc-url $BITTENSOR_RPC_URL
```

## How It Works

### Burn Flow

1. Contract holds staked TAO tokens (via forced send)
2. Anyone calls `burnAll()`
3. Contract calculates gas reimbursement: `(gasUsed + 90000) * tx.gasprice`
4. **Contract calls unstake precompile** to convert staked TAO to liquid TAO
5. Contract sends gas reimbursement to caller
6. **Contract sends remaining liquid TAO to address(0)** to permanently burn tokens
7. Event emitted with unstake amount, burn amount, and gas reimbursement

### Gas Reimbursement

The contract reimburses callers for gas costs to incentivize burns:

```
Example with 10 staked TAO:
- Gas used so far: ~10,000 units
- Reimbursement buffer: 90,000 units
- Total gas estimate: 100,000 units
- Gas price: 20 gwei
- Reimbursement: 100,000 * 20 gwei = 0.002 TAO
- Amount unstaked: 10 TAO
- Amount burned: 10 - 0.002 = 9.998 TAO
- Caller receives: 0.002 TAO (covers their gas cost)
```

## Security Considerations

### Trustless Design

- **No owner** - No single point of control
- **No admin functions** - Cannot be paused or modified
- **Stateless** - No storage to manipulate
- **Immutable** - Behavior fixed at deployment

### Audited Risks

1. **Gas Price Manipulation**: Callers using high gas prices pay for it upfront (net zero gain)
2. **Precompile Failure**: Function reverts, can be retried
3. **Insufficient Balance**: Reverts if balance < gas reimbursement
4. **Reentrancy**: No state to corrupt; uses checks-effects-interactions pattern
5. **Front-running**: First transaction wins; no value extraction beyond gas

### Invariants

- Contract balance ≈ 0 after successful burn (may have dust)
- Burned tokens are permanently destroyed
- Caller is always reimbursed (≥ actual gas cost)

### Recommendations

- Test thoroughly on testnet before mainnet
- Verify unstake precompile address for Bittensor
- Verify tokens sent to address(0) are permanently burned on the network
- Monitor contract events for unexpected behavior
- Calibrate REIMBURSEMENT_BUFFER on testnet if needed

## Gas Optimization

The contract is optimized for minimal gas usage:

- ✅ No state variables (no SSTORE/SLOAD)
- ✅ Custom errors instead of require strings
- ✅ Minimal computation
- ✅ Efficient event emissions

**Deployment cost**: ~460k gas
**burnAll() cost**: ~45-50k gas (varies with precompile)

## Events

```solidity
event Burned(
    uint256 amountUnstaked,    // Amount of staked tokens unstaked
    uint256 amountBurned,      // Amount of liquid tokens burned
    uint256 gasReimbursement,  // Amount sent to caller
    address indexed caller,     // Who triggered the burn
    uint256 timestamp          // Block timestamp
);
```

## Comparison with Original Design

| Feature | Original | Simplified |
|---------|----------|------------|
| Owner | ✅ Yes | ❌ No |
| Pause | ✅ Yes | ❌ No |
| receive() | ✅ Yes | ❌ No |
| State variables | 3 | 0 |
| Functions | 7 | 3 |
| Gas reimbursement | ❌ No | ✅ Yes |
| Trustless | ⚠️ Partial | ✅ Full |

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass (`forge test`)
5. Submit a pull request

## License

MIT

## Important Warnings

⚠️ **CRITICAL WARNINGS**

- Burned tokens are **PERMANENTLY DESTROYED**
- There is **NO RECOVERY MECHANISM**
- Contract has **NO ADMIN OR OWNER**
- Once deployed, **CANNOT BE MODIFIED**
- Verify precompile address **BEFORE DEPLOYMENT**
- **TEST ON TESTNET FIRST**

## Resources

- [Contract Specification](./BURN_CONTRACT_SPEC.md)
- [Foundry Book](https://book.getfoundry.sh/)
- [Bittensor Documentation](https://docs.bittensor.com/)
- [Solidity Documentation](https://docs.soliditylang.org/)

## FAQ

**Q: Why no receive() function?**
A: Prevents accidental deposits and simplifies the interface. Tokens must be intentionally force-sent.

**Q: Who can call burnAll()?**
A: Anyone! The contract is fully permissionless.

**Q: What if the burn fails?**
A: The transaction reverts, and you can retry. No tokens are lost.

**Q: How accurate is the gas reimbursement?**
A: Very accurate. The REIMBURSEMENT_BUFFER is calibrated to cover actual gas costs with a small safety margin.

**Q: Can the contract be paused or upgraded?**
A: No. It's completely immutable and trustless.

**Q: What happens if I send tokens directly?**
A: The transaction will fail. You must use a forced send mechanism (like selfdestruct).

## Contact

For issues or questions, please open an issue on GitHub.
- **Registration flow requirements**:
  - The hotkey passed to `registerNeuron`/`burnedRegisterNeuron` must be a fresh 32-byte key (convert an SS58 using `tools/register_neuron.py` or generate one with `tools/generate_h160_keypair.py`). The contract assumes ownership of that hotkey; no other coldkey should be associated with it.
  - The contract’s own address effectively acts as the coldkey, so it must hold enough TAO to cover the registration burn. You can top it up by converting the contract’s `0x` address to SS58 via `tools/h160_to_ss58.py` and sending TAO on-chain. Check the required burn amount via `btcli subnet show --netuid <id> --network <name>` (e.g., `btcli subnet show --netuid 285 --network test` on testnet).
