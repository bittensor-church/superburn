// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title Sink
 * @notice A minimal, trustless contract that burns staked TAO tokens on Bittensor
 * @dev This contract is completely stateless and has no administrative functions.
 *      Anyone can call burnAll() to unstake and burn the contract's balance and receive gas reimbursement.
 *
 * Process: Unstake staked TAO → Burn liquid TAO
 *
 * Design principles:
 * - No owner, no admin, no pause
 * - No state variables (fully stateless)
 * - No receive() function (tokens must be force-sent)
 * - Single public function: burnAll()
 * - Gas reimbursement for callers
 */
contract Sink {
    // ============ Constants ============

    /// @notice Address of the unstake precompile on Bittensor
    address private constant UNSTAKE_PRECOMPILE = 0x0000000000000000000000000000000000000801;

    /// @notice Address of the neuron (burned register) precompile on Bittensor
    address private constant NEURON_PRECOMPILE = 0x0000000000000000000000000000000000000804;

    /// @notice Gas buffer for reimbursement calculation (calibrated through testing)
    /// @dev Covers: unstake call (~30k) + reimbursement transfer (~30k) + burn to address(0) (~21k) + event (~5k) + safety margin
    uint256 private constant REIMBURSEMENT_BUFFER = 90000;

    // ============ Events ============

    /// @notice Emitted when tokens are unstaked and burned
    /// @param amountUnstaked Amount of staked tokens unstaked via precompile
    /// @param amountBurned Amount of liquid tokens burned (sent to address(0))
    /// @param gasReimbursement Amount of tokens sent to caller as gas reimbursement
    /// @param caller Address that triggered the burn
    /// @param timestamp Block timestamp of the burn
    event Burned(
        uint256 amountUnstaked,
        uint256 amountBurned,
        uint256 gasReimbursement,
        address indexed caller,
        uint256 timestamp
    );

    /// @notice Emitted when contract registers a neuron through the precompile
    /// @param netuid Subnet identifier
    /// @param hotkey Hotkey used for registration
    /// @param amountBurned Amount of TAO sent (burned) during registration
    /// @param caller Address that initiated the registration
    event Registered(uint16 indexed netuid, bytes32 hotkey, uint256 amountBurned, address indexed caller);

    // ============ Errors ============

    /// @dev Thrown when contract balance is insufficient to cover gas reimbursement
    error InsufficientBalance();

    /// @dev Thrown when unstake precompile call fails
    error UnstakeFailed();

    /// @dev Thrown when gas reimbursement transfer fails
    error ReimbursementFailed();

    /// @dev Thrown when burn to address(0) fails
    error BurnFailed();

    /// @dev Thrown when burnedRegister call fails
    error BurnedRegisterFailed();

    // ============ Public Functions ============

    /**
     * @notice Unstakes and burns all tokens held by the contract, reimburses the caller for gas
     * @dev This function:
     *      1. Calculates gas reimbursement based on tx.gasprice and gas estimates
     *      2. Unstakes all staked TAO tokens via the unstake precompile
     *      3. Sends gas reimbursement to msg.sender
     *      4. Burns remaining liquid balance by sending to address(0)
     *      5. Emits Burned event
     *
     * Gas reimbursement formula:
     *   gasReimbursement = (gasUsedSoFar + REIMBURSEMENT_BUFFER) * tx.gasprice
     *
     * The REIMBURSEMENT_BUFFER is calibrated to cover:
     *   - Gas for the unstake precompile call
     *   - Gas for the reimbursement transfer
     *   - Gas for the burn to address(0)
     *   - Gas for event emission
     *   - Safety margin for variations
     *
     * @return success True if unstake and burn were successful
     *
     * Reverts:
     *   - InsufficientBalance: if balance <= estimated gas cost
     *   - UnstakeFailed: if unstake precompile call fails
     *   - ReimbursementFailed: if transfer to caller fails
     *   - BurnFailed: if burn to address(0) fails
     */
    function burnAll() external returns (bool success) {
        // Record gas at function start
        uint256 startGas = gasleft();

        // Get current balance (staked TAO)
        uint256 balance = address(this).balance;

        // Calculate gas used so far and estimate total gas needed
        uint256 gasUsedSoFar = startGas - gasleft();
        uint256 totalGasEstimate = gasUsedSoFar + REIMBURSEMENT_BUFFER;

        // Calculate gas reimbursement amount
        uint256 gasReimbursement = totalGasEstimate * tx.gasprice;

        // Ensure we have enough balance to both reimburse and burn something
        if (balance <= gasReimbursement) revert InsufficientBalance();

        // Step 1: Unstake all staked TAO tokens
        (bool unstakeSuccess,) = UNSTAKE_PRECOMPILE.call(
            abi.encodeWithSignature("unstake(uint256)", balance)
        );
        if (!unstakeSuccess) revert UnstakeFailed();

        // Step 2: Reimburse caller for gas costs
        (bool reimbursementSuccess,) = msg.sender.call{value: gasReimbursement}("");
        if (!reimbursementSuccess) revert ReimbursementFailed();

        // Step 3: Burn remaining liquid balance by sending to address(0)
        uint256 amountToBurn = balance - gasReimbursement;
        (bool burnSuccess,) = payable(address(0)).call{value: amountToBurn}("");
        if (!burnSuccess) revert BurnFailed();

        // Emit event for tracking (unstaked amount, burned amount, gas reimbursement)
        emit Burned(balance, amountToBurn, gasReimbursement, msg.sender, block.timestamp);

        return true;
    }

    /**
     * @notice Returns the current balance of the contract (staked TAO)
     * @dev Useful for checking if there are tokens to unstake and burn
     * @return Current staked balance in wei
     */
    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }

    /**
     * @notice Estimates the gas reimbursement for a burnAll() call at current gas price
     * @dev This is an approximation. Actual gas used may vary slightly.
     *      Includes gas for unstaking, reimbursement, burning, and event emission.
     * @return Estimated gas reimbursement amount in wei
     */
    function estimateReimbursement() external view returns (uint256) {
        // Base estimate: assume ~5000 gas used before reimbursement calculation
        // This is a rough estimate and may vary based on network conditions
        uint256 estimatedGasUsage = 5000 + REIMBURSEMENT_BUFFER;
        return estimatedGasUsage * tx.gasprice;
    }

    /**
     * @notice Registers a neuron via the burnedRegister precompile.
     * @dev Forwards msg.value to the precompile so the required TAO burn is covered.
     * @param netuid Subnet identifier to register within
     * @param hotkey 32-byte hotkey used for neuron identity
     * @return success True when the precompile call succeeds
     */
    function registerNeuron(uint16 netuid, bytes32 hotkey) external payable returns (bool success) {
        (bool callSuccess, bytes memory returnData) = NEURON_PRECOMPILE.call{value: msg.value}(
            abi.encodeWithSignature("burnedRegister(uint16,bytes32)", netuid, hotkey)
        );
        if (!callSuccess) {
            if (returnData.length > 0) {
                assembly {
                    revert(add(returnData, 0x20), mload(returnData))
                }
            }
            revert BurnedRegisterFailed();
        }

        emit Registered(netuid, hotkey, msg.value, msg.sender);
        return true;
    }
}
