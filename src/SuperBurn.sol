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
    address public owner;

    /// @notice Emitted when stake is removed and burned.
    event UnstakedAndBurned(bytes32 indexed hotkey, uint256 amount, uint256 burnedAmount);

    /// @notice Emitted for every register call (success or fail).
    event RegisterAttempt(
        uint16 indexed netuid,
        bytes32 hotkey,
        uint256 amountBurned,
        address indexed caller,
        bool success
    );

    error InsufficientValue();
    error RefundFailed();

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    /// @notice Allows the contract to receive TAO.
    receive() external payable {}

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

            // 1. Call removeStake on the precompile
            bytes memory data = abi.encodeWithSelector(
                Staking.removeStake.selector,
                hotkeys[i],
                amounts[i],
                netuid
            );

            (bool success, ) = STAKING_PRECOMPILE.call(data);
            require(success, "removeStake call failed");
        }

        uint256 totalReceivedTao = address(this).balance - balanceBeforeAll;
        require(totalReceivedTao > 0, "No TAO received");

        uint256 gasUsed = gasStart - gasleft();
        uint256 refundAmount = gasUsed * tx.gasprice;

        if (refundAmount > totalReceivedTao) {
            refundAmount = totalReceivedTao;
        }

        if (refundAmount > 0) {
            (bool refundSuccess, ) = payable(msg.sender).call{value: refundAmount}("");
            require(refundSuccess, "Gas refund failed");
        }

        uint256 burnAmount = totalReceivedTao - refundAmount;

        if (burnAmount > 0) {
            (bool burnSuccess, ) = payable(BURN_ADDRESS).call{value: burnAmount}("");
            require(burnSuccess, "Burn failed");
        }
    }

    /// @notice Registers a neuron using burned TAO.
    /// @param netuid Network UID.
    /// @param hotkey Hotkey to register.
    /// @param amountToBurn Amount of TAO that will be burned for registration.
    function burnedRegisterNeuron(
        uint16 netuid,
        bytes32 hotkey,
        uint256 amountToBurn
    ) external payable returns (bool) {
        if (amountToBurn == 0) revert InsufficientValue();
        uint256 startingBalance = address(this).balance;

        if (startingBalance < amountToBurn) revert InsufficientValue();

        bytes memory data = abi.encodeWithSelector(
            bytes4(keccak256("burnedRegister(uint16,bytes32)")),
            netuid,
            hotkey
        );

        (bool success,) = NEURON_PRECOMPILE.call{value: amountToBurn, gas: gasleft()}(data);

        if (!success) {
            _refund(startingBalance);
            emit RegisterAttempt(netuid, hotkey, amountToBurn, msg.sender, false);
            return false;
        }

        // Refund leftover balance
        uint256 leftover = address(this).balance;
        if (leftover > 0) _refund(leftover);

        emit RegisterAttempt(netuid, hotkey, amountToBurn, msg.sender, true);
        return true;
    }

    function _refund(uint256 amount) internal {
        (bool sent,) = payable(msg.sender).call{value: amount}("");
        if (!sent) revert RefundFailed();
    }
}
