// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

address constant STAKING_PRECOMPILE = 0x0000000000000000000000000000000000000805;

address constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;

interface Staking {

    function addStake(bytes32 hotkey, uint256 amount, uint256 netuid) external;

    function removeStake(
        bytes32 hotkey,
        uint256 amount,
        uint256 netuid
    ) external;
}


contract ProperSink {
    address public owner;
    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    receive() external payable {}

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
    }

    function removeStakeAndBurn(
        bytes32 hotkey,
        uint256 netuid,
        uint256 amount
    ) external onlyOwner {
        bytes memory data = abi.encodeWithSelector(
            Staking.removeStake.selector,
            hotkey,
            amount,
            netuid
        );

        (bool success, ) = STAKING_PRECOMPILE.call{gas: gasleft()}(data);
        require(success, "removeStake call failed");

        (bool burnSuccess, ) = payable(BURN_ADDRESS).call{value: amount}("");
        require(burnSuccess, "Burn failed");
    }
}