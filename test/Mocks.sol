// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../src/SuperBurn.sol";

contract ForceSender {
    constructor(address payable _to) payable {
        selfdestruct(_to);
    }
}

contract MockStaking {
    bool public shouldFail;

    function addStake(bytes32, uint256, uint256) external payable {
        if (shouldFail) {
            revert("Mock: addStake failed");
        }
    }

    function removeStake(bytes32, uint256 amount, uint256) external {
        if (shouldFail) {
            revert("Mock: removeStake failed");
        }
        if (amount > 0) {
            new ForceSender{value: amount}(payable(msg.sender));
        }
    }

    function setShouldFail(bool _fail) external {
        shouldFail = _fail;
    }
}

contract MockNeuron {
    bool public shouldFail;

    function burnedRegister(uint16, bytes32) external payable {
        if (shouldFail) {
            revert("Mock: burnedRegister failed");
        }
    }

    function setShouldFail(bool _fail) external {
        shouldFail = _fail;
    }
}

contract RevertingReceiver {
    function callRegister(address _target, uint16 _netuid, bytes32 _hotkey) external payable {
        SuperBurn(_target).registerNeuron{value: msg.value}(_netuid, _hotkey);
    }

    function callUnstake(address _target, bytes32[] calldata _hotkeys, uint256 _netuid, uint256[] calldata _amounts) external {
        SuperBurn(_target).unstakeAndBurn(_hotkeys, _netuid, _amounts);
    }

    receive() external payable {
        revert("I refuse refunds");
    }
}