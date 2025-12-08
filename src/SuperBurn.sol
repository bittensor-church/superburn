// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @dev Address of the Bittensor Staking Precompile contract.
address constant STAKING_PRECOMPILE = 0x0000000000000000000000000000000000000805;

/// @dev Address of the Neuron Registration Precompile contract.
address constant NEURON_PRECOMPILE = 0x0000000000000000000000000000000000000804;

/// @dev Address where tokens are sent to be burned.
address constant BURN_ADDRESS = 0x0000000000000000000000000000000000000000;

interface Staking {
    function addStake(bytes32 hotkey, uint256 amount, uint256 netuid) external;
    function removeStake(bytes32 hotkey, uint256 amount, uint256 netuid) external;
}

contract SuperBurn {

    /// @notice Emitted for successful register call
    event NeuronRegistration(
        uint16 indexed netuid,
        bytes32 hotkey,
        address indexed caller
    );

    error NeuronRegistrationFailed();
    error RemoveStakeError();
    error BurnError();
    error RefundError();
    error ReceivedTaoIsZeroError();

    constructor() {}

    /// @notice Internal function to handle safe refunds to the user.
    /// @param recipient The address to receive the refund.
    /// @param amount The amount to refund.
    function _processRefund(address recipient, uint256 amount) private {
        if (amount > 0) {
            (bool success, ) = payable(recipient).call{value: amount}("");
            if (!success) {
                revert RefundError();
            }
        }
    }

    /// @notice Unstakes TAO from validators and immediately burns it.
    /// @dev This function is open to everyone. Anyone can trigger the burn mechanism.
    /// @param hotkeys Array of validator hotkeys to unstake from.
    /// @param netuid The network UID.
    /// @param amounts Array of amounts (in Rao) to unstake corresponding to hotkeys.
    function unstakeAndBurn(
        bytes32[] calldata hotkeys,
        uint256 netuid,
        uint256[] calldata amounts
    ) external {
        require(hotkeys.length == amounts.length, "Length mismatch");

        uint256 gasStart = gasleft();
        uint256 balanceBeforeAll = address(this).balance;

        for (uint256 i = 0; i < hotkeys.length; i++) {

            bytes memory data = abi.encodeWithSelector(
                Staking.removeStake.selector,
                hotkeys[i],
                amounts[i],
                netuid
            );

            (bool success, ) = STAKING_PRECOMPILE.call(data);
            if (!success) {
                revert RemoveStakeError();
            }
        }

        uint256 totalReceivedTao = address(this).balance - balanceBeforeAll;
        if (totalReceivedTao == 0) {
            revert ReceivedTaoIsZeroError();
        }

        uint256 gasUsed = gasStart - gasleft();
        uint256 refundAmount = gasUsed * tx.gasprice;

        if (refundAmount > totalReceivedTao) {
            refundAmount = totalReceivedTao;
        }

        _processRefund(msg.sender, refundAmount);

        uint256 burnAmount = totalReceivedTao - refundAmount;

        if (burnAmount > 0) {
            (bool burnSuccess, ) = payable(BURN_ADDRESS).call{value: burnAmount}("");
            if (!burnSuccess) {
                revert BurnError();
            }
        }
    }

    /// @notice Registers a neuron using burned TAO.
    /// @param netuid Network UID.
    /// @param hotkey Hotkey to register.
    function registerNeuron(
        uint16 netuid,
        bytes32 hotkey
    ) external payable returns (bool) {
        bytes memory data = abi.encodeWithSelector(
            bytes4(keccak256("burnedRegister(uint16,bytes32)")),
            netuid,
            hotkey
        );

        uint256 balanceBefore = address(this).balance;

        (bool success, ) = NEURON_PRECOMPILE.call{value: 0, gas: gasleft()}(
            data
        );

        if (!success) {
            revert NeuronRegistrationFailed();
        }

        uint256 balanceAfter = address(this).balance;

        uint256 burnedAmount = balanceBefore - balanceAfter;

        if (msg.value > burnedAmount) {
            _processRefund(msg.sender, msg.value - burnedAmount);
        }

        emit NeuronRegistration(netuid, hotkey, msg.sender);
        return true;
    }
}