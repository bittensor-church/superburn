// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract RegisterOnly {
    address constant NEURON_PRECOMPILE = 0x0000000000000000000000000000000000000804;

    event RegisterAttempt(uint16 indexed netuid, bytes32 hotkey, uint256 amountBurned, address indexed caller, bool success);

    error InsufficientValue();
    error RefundFailed();

    receive() external payable {}

    function burnedRegisterNeuron(uint16 netuid, bytes32 hotkey, uint256 amountToBurn) external payable returns (bool) {
        if (amountToBurn == 0) revert InsufficientValue();
        uint256 startingBalance = address(this).balance;
        if (startingBalance < amountToBurn) revert InsufficientValue();

        bytes memory data = abi.encodeWithSelector(bytes4(keccak256("burnedRegister(uint16,bytes32)")), netuid, hotkey);
        (bool success,) = NEURON_PRECOMPILE.call{value: amountToBurn, gas: gasleft()}(data);

        if (!success) {
            _refund(startingBalance);
            emit RegisterAttempt(netuid, hotkey, amountToBurn, msg.sender, false);
            return false;
        }

        // Refund any remaining balance to the caller (e.g., prefund minus amountToBurn).
        uint256 leftover = address(this).balance;
        if (leftover > 0) _refund(leftover);
        emit RegisterAttempt(netuid, hotkey, amountToBurn, msg.sender, true);
        return true;
    }

    function _refund(uint256 amount) internal {
        (bool refundSuccess,) = payable(msg.sender).call{value: amount}("");
        if (!refundSuccess) revert RefundFailed();
    }
}
