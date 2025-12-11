# SuperBurn – Bittensor Burn Police Contract

SuperBurn is a purpose-built smart contract for punishing fraudulent Bittensor subnets. It registers as a miner on target subnets so incentives can flow to it. Validators (the “burn police”) direct subnet incentives to the contract; anyone can then trigger a burn that drains the contract’s accumulated alpha, converts it to TAO, and burns it. Burns reimburse most (not all) of the caller gas, so enforcement stays permissionless and cheap (the registration fee still needs to be covered).

> **Status:** Deployed on mainnet. Contract H160 [`0x2f47AfDE4e8CC372B8Edd794B3492b3479c260eE`](https://evm.taostats.io/address/0x2f47AfDE4e8CC372B8Edd794B3492b3479c260eE) and SS58 [`5D7vUnt4TJ6M8aQbriZCMMkZ8sfYsSJJvRrVnhdWzkArVHDh`](https://taostats.io/account/5D7vUnt4TJ6M8aQbriZCMMkZ8sfYsSJJvRrVnhdWzkArVHDh). Registration/burn scripts live in [`tools/`](tools).

## Why SuperBurn?
- Redirect and destroy rewards earned by malicious subnets, stopping TAO leakage to subnet owners.
- Permissionless execution: any account can run the burn script; caller gas is mostly reimbursed.
- Minimal trust: no profit extraction pathway; incentives are dictated by validator weights.

## Design Principles
- 🔓 **No admin on burn path** – Burning is permissionless and there is no withdrawal path for TAO.
- 🤖 **Validator-directed incentives** – Weights steer rewards; the contract itself cannot capture value.
- 💰 **Gas-reimbursed enforcement** – Burn callers are mostly reimbursed; only registration fees must be covered.
- 🎯 **Minimal surface** – Core flows are registration + burn.
- 🔒 **Immutable deployment** – No upgrades planned once live.

## How It Works
1) **Register as a miner:** SuperBurn self-registers on a target subnet (run `tools/register_neuron.py` to call `burnedRegisterNeuron` on the contract).  
2) **Weights set by validators:** Policing validators set weights so all subnet incentives flow to SuperBurn. (Weight-setting is off-chain governance; the contract is not enforcing it.)  
3) **Alpha accrues:** Rewards accrue as alpha under the contract’s coldkey.  
4) **Burn trigger:** Anyone runs `tools/unstake_and_burn.py`, which calls `unstakeAndBurn(...)` to unstake all alpha into TAO and immediately burn to `0x000...0000`.  
5) **Gas reimbursement:** The contract repays most of the caller gas, keeping enforcement cheap (registration fee still needs funding).

Effect on a fraudulent subnet: alpha price is nosediving, TAO is drained from its liquidity, and outflows dry up emissions; value shifts back to honest subnets.

## Contract Surface (SuperBurn.sol)
- **Registration:** `burnedRegisterNeuron(netuid, hotkey)` forwards to the neuron precompile so the contract can self-register as a miner. This consumes the subnet registration fee and gas from the contract balance (not reimbursable).  
- **Burning:** `unstakeAndBurn(hotkeys[], netuid, amounts[])` unstakes specified positions, converts alpha to TAO, reimburses most of the caller’s gas, then burns all TAO.  

Burn target is `0x0000000000000000000000000000000000000000`.

## Detailed Workflow
1) **Prep**  
   - `pip install -r requirements.txt` for tooling.  
   - Need a fresh EVM wallet? Generate one with `python tools/generate_h160_keypair.py` and fund it by sending TAO to the SS58 it prints.  
   - Export `PRIVATE_KEY` for tx signing.
2) **Register SuperBurn as a miner (per subnet)**  
   - Contract addresses: H160 `0x2f47AfDE4e8CC372B8Edd794B3492b3479c260eE`, SS58 `5D7vUnt4TJ6M8aQbriZCMMkZ8sfYsSJJvRrVnhdWzkArVHDh`.  
   - Generate a loose coldkey (will serve as the contract's hotkey): `btcli wallet new-coldkey` and capture its public key (e.g., from `~/.bittensor/wallets/<name>/coldkeypub.txt`). This coldkey becomes the registered hotkey tied to the SuperBurn coldkey, so incentives flow to the contract balance.  
   - Ensure your caller EVM wallet has enough TAO: the register tool transfers TAO to the contract, pays the registration fee and gas, then sends back any leftover TAO.  
   - Use the registration helper (see [Registering the SuperBurn miner](#registering-the-superburn-miner-helper) below).
3) **Validator weight-setting**  
   - Validators set weights directing emissions to the SuperBurn hotkey (outside contract control).
4) **Monitor alpha**  
   - Track the contract coldkey [`5D7vUnt4TJ6M8aQbriZCMMkZ8sfYsSJJvRrVnhdWzkArVHDh`](https://taostats.io/account/5D7vUnt4TJ6M8aQbriZCMMkZ8sfYsSJJvRrVnhdWzkArVHDh) on taostats to see accrued alpha.
5) **Burn**  
   - Trigger the contract to unstake and burn accumulated alpha using the burn helper (see [Triggering a burn](#triggering-a-burn-helper) below). The contract reimburses most of the gas while burning the TAO.

### Registering the SuperBurn miner (helper)
Requires: a loose coldkey (public key) from `btcli wallet new-coldkey`, `PRIVATE_KEY` set in your environment and the deployed contract address.
```bash
python tools/register_neuron.py \
  --netuid SUBNET_ID \
  --network finney \
  --hotkey-pub 0xNewColdkeyPublicKey \
  0x2f47AfDE4e8CC372B8Edd794B3492b3479c260eE
```
`--hotkey-pub` is the 32-byte public key of the coldkey that will serve as the registered hotkey on the subnet; the final positional argument is the contract address.


### Triggering a burn (helper)
Requires: `PRIVATE_KEY` set in your environment and the deployed contract address.
```bash
python tools/unstake_and_burn.py \
  --netuid SUBNET_ID \
  --network finney \
  0x2f47AfDE4e8CC372B8Edd794B3492b3479c260eE
```
The script fetches stake for the contract coldkey, builds the `unstakeAndBurn` call, and the contract reimburses most of the gas while burning the TAO.

## Tooling
- `tools/register_neuron.py` – Register the SuperBurn miner.  
- `tools/unstake_and_burn.py` – Fetch contract-owned stake and trigger the burn.  
- `tools/get_all_validators_and_stake.py` – Inspect validator stake positions.  
- `tools/generate_h160_keypair.py` – Key/address utility (backed by `tools/utils/address_converter.py`).  

## Deployment Notes
- Contract is already deployed on mainnet (see Status above). If you need to redeploy, use `script/Deploy.s.sol`.
- Foundry is only needed if you plan to build or deploy the contract yourself; using the provided tooling does not require it. Install from https://getfoundry.sh/introduction/installation/.  
- Example deploy:  
  ```bash
  forge install foundry-rs/forge-std
  forge script script/Deploy.s.sol \
    --rpc-url "https://lite.chain.opentensor.ai" \
    --broadcast
  ```
  Note the deployed contract address from the script output for your records.
- After deployment, verify the contract on taostats so everyone can inspect the source before using it.
- Env vars:  
  - `PRIVATE_KEY` – signer for deploy/ops  
- Build/test:  
  ```bash
  forge build
  forge test
  ```

## Safety & Invariants
- Burns are irreversible; all TAO reaching the burn step is destroyed.  
- No withdrawal path; contract cannot surface TAO once staked or burned.  
- Gas reimbursement should make burns close to economically neutral for the caller (verify with your RPC’s gas price).  
- Weight-setting is external; ensure validator consensus before relying on the mechanism.  
- Verify precompile addresses against the current Bittensor release before deployment.

## FAQ
- **Who can trigger a burn?** Anyone; the contract reimburses most gas to keep it cheap.  
- **Can someone keep the alpha or TAO?** No; `unstakeAndBurn` always routes unstaked TAO to the burn address.  
- **What stops a malicious operator from resetting weights?** Only validator coordination—contract code cannot enforce weights.  
- **How do I know how much alpha to burn?** Check the contract coldkey [`5D7vUnt4TJ6M8aQbriZCMMkZ8sfYsSJJvRrVnhdWzkArVHDh`](https://taostats.io/account/5D7vUnt4TJ6M8aQbriZCMMkZ8sfYsSJJvRrVnhdWzkArVHDh) on taostats. The burn helper fetches current stake and burns all of it.  
- **Does this hurt honest subnets?** The mechanism is opt-in per subnet and only works where validators route weights to SuperBurn.
