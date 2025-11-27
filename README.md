# SuperBurn – Bittensor Burn Police Contract

SuperBurn is a purpose-built smart contract for punishing fraudulent Bittensor subnets. It registers as a miner on target subnets so incentives can flow to it. Validators (the “burn police”) direct subnet incentives to the contract; anyone can then trigger a burn that drains the contract’s accumulated alpha, converts it to TAO, and burns it. Burns reimburse the caller for gas, so enforcement stays permissionless and cheap (only the registration fee needs to be covered).

> **Status:** Deployed on mainnet. The contract H160 is `0x...` and its SS58 is `5...` (replace with real values when published). View it on `https://evm.taostats.io/address/0x...` and check the contract balance on taostats via `https://taostats.io/account/<coldkey>`. Registration/burn scripts are provided in `tools/`.

## Why SuperBurn?
- Redirect and destroy rewards earned by malicious subnets, stopping TAO leakage to subnet owners.
- Permissionless execution: any account can run the burn script; caller gas is reimbursed.
- Minimal trust: no profit extraction pathway; incentives are dictated by validator weights.

## Design Principles
- 🔓 **No admin on burn path** – Burning is permissionless and there is no withdrawal path for TAO.
- 🤖 **Validator-directed incentives** – Weights steer rewards; the contract itself cannot capture value.
- 💰 **Gas-reimbursed enforcement** – Burn callers are reimbursed; only registration fees must be covered.
- 🎯 **Minimal surface** – Core flows are registration + burn; staking helper is gated and mainly for testing.
- 🔒 **Immutable deployment** – No upgrades planned once live.

## How It Works
1) **Register as a miner:** SuperBurn self-registers on a target subnet (uses the `burnedRegisterNeuron` helper from `RegisterOnly.sol`).  
2) **Weights set by validators:** Policing validators set weights so all subnet incentives flow to SuperBurn. (Weight-setting is off-chain governance; the contract is not enforcing it.)  
3) **Alpha accrues:** Rewards accrue as alpha under the contract’s coldkey.  
4) **Burn trigger:** Anyone runs `tools/unstake_and_burn.py`, which calls `unstakeAndBurn(...)` to unstake all alpha into TAO and immediately burn to `0x000...0000`.  
5) **Gas reimbursement:** The contract repays the caller for gas, making the burn effectively free for the enforcer.

Effect on a fraudulent subnet: alpha price is nosediving, TAO is drained from its liquidity, and outflows dry up emissions; value shifts back to honest subnets.

## Contract Surface (SuperBurn.sol)
- **Registration (core):** `burnedRegisterNeuron(netuid, hotkey)` forwards to the neuron precompile so the contract can self-register as a miner. This consumes the subnet registration fee and gas from the contract balance (not reimbursable).  
- **Burning (core):** `unstakeAndBurn(hotkeys[], netuid, amounts[])` unstakes specified positions, converts alpha to TAO, reimburses the caller’s gas, then burns all TAO.  
- **Staking (utility/testing):** `stake(hotkey, netuid, amount)` (owner-gated) can stake TAO to a hotkey; primarily for testing flows.  
- **Receives TAO:** payable `receive()` to accept inflows (needed to fund registration fees and staking); no withdraw path.

Burn target is `0x0000000000000000000000000000000000000000`.

## Usage at a Glance
1) **Prep**  
   - `pip install -r requirements.txt` for tooling.  
   - Need a fresh EVM wallet? Generate one with `python tools/generate_h160_keypair.py` and fund it by sending TAO to the SS58 it prints.  
   - Export `PRIVATE_KEY` for tx signing.
2) **Register SuperBurn as a miner (per subnet)**  
   - Contract addresses: H160 `0x...`, SS58 `5...` (populate once published).  
   - Generate a loose coldkey (will serve as the contract's hotkey): `btcli wallet new-coldkey` and capture its public key (e.g., from `~/.bittensor/wallets/<name>/coldkeypub.txt`). This coldkey becomes the registered hotkey tied to the SuperBurn coldkey, so incentives flow to the contract balance.  
   - Check the registration fee: `btcli subnet show --netuid <subnet_id>`.  
   - Ensure your caller EVM wallet has enough TAO: the register tool transfers TAO to the contract, pays the registration fee and gas, then sends back any leftover TAO.  
   - Use the registration helper (instructions to follow with the target subnet details).
3) **Validator weight-setting**  
   - Validators set weights directing emissions to the SuperBurn hotkey. (Use `tools/set_weights.py` if desired; outside contract control.)
4) **Monitor alpha**  
   - Track the contract coldkey `XXX` on taostats via `https://taostats.io/account/<coldkey>` to see accrued alpha.
5) **Burn**  
   - Run `python tools/unstake_and_burn.py <contract> --netuid <subnet_id> --rpc-url https://lite.chain.opentensor.ai --private-key $PRIVATE_KEY`  
   - The script fetches stake for the contract coldkey, calls `unstakeAndBurn`, and the contract reimburses gas while burning all TAO.

### Registering the SuperBurn miner (example workflow)
- Requirements: deployed contract address, a loose coldkey (public key) from `btcli new-coldkey`, and an RPC endpoint.  
- Example:  
  ```bash
  python tools/register_neuron_minimal.py \
    --netuid <subnet_id> \
    --value-tao <enough tao for registration and gas fees> \
    --rpc-url https://lite.chain.opentensor.ai \
    --hotkey-bytes 0xNewColdkeyPublicKey \
    0xContractsAddress
  ```
  `--hotkey-bytes` is the 32-byte public key of the coldkey that will serve as the registered hotkey on the subnet; the final positional argument is the contract address.

## Tooling
- `tools/register_neuron_minimal.py` / `tools/register_neuron.py` – Register the SuperBurn miner.  
- `tools/unstake_and_burn.py` – Fetch contract-owned stake and trigger the burn.  
- `tools/get_all_validators_and_stake.py` – Inspect validator stake positions.  
- `tools/generate_h160_keypair.py` – Key/address utility (backed by `tools/utils/address_converter.py`).  
- `tools/set_weights.py` – Set validator weights (for validator operators).  
- `tools/stake.py` – Manually stake TAO to a hotkey via the contract (utility/testing).  

## Deployment Notes
- Mainnet address will be published here once ready.  
- Scripts: `script/Deploy.s.sol` for SuperBurn, `script/DeployRegisterOnly.s.sol` for the registration helper.  
- Foundry is only needed if you plan to build or deploy the contract yourself; using the provided tooling does not require it. Install from https://getfoundry.sh/introduction/installation/.  
- Example deploy (mainnet RPC):  
  ```bash
  forge install foundry-rs/forge-std
  forge script script/Deploy.s.sol \
    --rpc-url "https://lite.chain.opentensor.ai" \
    --broadcast
  ```
  Note the deployed contract address from the script output for your records.
- Verify the deployed contract on taostats (so the source is visible and easily inspectable):  
  ```bash
  forge verify-contract 0xYourContractAddress src/SuperBurn.sol:SuperBurn \
    --rpc-url "https://evm.taostats.io/api/eth-rpc" \
    --verifier blockscout \
    --verifier-url "https://evm.taostats.io/api/"
  ```
- Env vars:  
  - `PRIVATE_KEY` – signer for deploy/ops  
  - `BITTENSOR_RPC_URL` – mainnet RPC  
  - `BITTENSOR_TESTNET_RPC_URL` – testnet RPC (if testing)  
- Build/test:  
  ```bash
  forge build
  forge test
  ```

## Safety & Invariants
- Burns are irreversible; all TAO reaching the burn step is destroyed.  
- No withdrawal path; contract cannot surface TAO once staked or burned.  
- Gas reimbursement should make burns economically neutral for the caller (verify with your RPC’s gas price).  
- Weight-setting is external; ensure validator consensus before relying on the mechanism.  
- Verify precompile addresses against the current Bittensor release before deployment.

## FAQ
- **Who can trigger a burn?** Anyone; the contract reimburses gas to keep it free.  
- **Can someone keep the alpha or TAO?** No; `unstakeAndBurn` always routes unstaked TAO to the burn address.  
- **What stops a malicious operator from resetting weights?** Only validator coordination—contract code cannot enforce weights.  
- **How do I know how much alpha to burn?** Check the contract coldkey `XXX` on taostats via `https://taostats.io/account/<coldkey>`; the burn script also reports totals before execution.  
- **Does this hurt honest subnets?** The mechanism is opt-in per subnet and only works where validators route weights to SuperBurn.
