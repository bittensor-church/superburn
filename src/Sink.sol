// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @dev Address of the Bittensor Staking Precompile contract.
address constant STAKING_PRECOMPILE = 0x0000000000000000000000000000000000000805;

/// @dev Address where tokens are sent to be burned.
address constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;

interface Staking {
    function addStake(bytes32 hotkey, uint256 amount, uint256 netuid) external;
    function removeStake(bytes32 hotkey, uint256 amount, uint256 netuid) external;
}

contract Sink {
    address public owner;

    /// @notice Emitted when the owner adds stake.
    event StakeAdded(bytes32 indexed hotkey, uint256 amount, uint256 netuid);

    /// @notice Emitted when stake is removed and burned.
    event UnstakedAndBurned(bytes32 indexed hotkey, uint256 amount, uint256 burnedAmount);

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    /// @notice Allows the contract to receive TAO.
    receive() external payable {}

    /// @notice Stakes TAO to a validator. Only the owner can call this.
    /// @param hotkey The validator's hotkey (32 bytes).
    /// @param netuid The network UID (e.g., 1 for root).
    /// @param amount The amount of Rao to stake.
    function stake(
        bytes32 hotkey,
        uint256 netuid,
        uint256 amount
    ) external onlyOwner {
        bytes memory data = abi.encodeWithSelector(
            Staking.addStake.selector,
            hotkey,
            amount,
            netuid
        );

        (bool success, ) = STAKING_PRECOMPILE.call{gas: gasleft()}(data);
        require(success, "addStake call failed");

        emit StakeAdded(hotkey, amount, netuid);
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

        for (uint256 i = 0; i < hotkeys.length; i++) {
            uint256 balanceBefore = address(this).balance;

            // 1. Call removeStake on the precompile
            bytes memory data = abi.encodeWithSelector(
                Staking.removeStake.selector,
                hotkeys[i],
                amounts[i],
                netuid
            );

            (bool success, ) = STAKING_PRECOMPILE.call{gas: gasleft()}(data);
            require(success, "removeStake call failed");

            // 2. Calculate received TAO (delta balance)
            uint256 balanceAfter = address(this).balance;
            uint256 receivedTao = balanceAfter - balanceBefore;

            // 3. Burn the received TAO if any
            if (receivedTao > 0) {
                (bool burnSuccess, ) = payable(BURN_ADDRESS).call{value: receivedTao}("");
                require(burnSuccess, "Burn failed");

                emit UnstakedAndBurned(hotkeys[i], amounts[i], receivedTao);
            }
        }
    }
}