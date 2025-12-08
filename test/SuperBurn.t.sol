// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/SuperBurn.sol";
import "./Mocks.sol";

contract SuperBurnTest is Test {
    SuperBurn public superBurn;
    MockStaking public stakingMock;
    MockNeuron public neuronMock;
    RevertingReceiver public revertingReceiver;

    address constant TARGET_STAKING = 0x0000000000000000000000000000000000000805;
    address constant TARGET_NEURON = 0x0000000000000000000000000000000000000804;
    address constant TARGET_BURN = 0x0000000000000000000000000000000000000000;

    address user = address(0x1234);

    bytes32 hotkey = bytes32(uint256(1));
    uint16 netuid = 1;

    event NeuronRegistration(uint16 indexed netuid, bytes32 hotkey, address indexed caller);
    event UnstakedAndBurned(bytes32 indexed hotkey, uint256 amount, uint256 burnedAmount);

    function setUp() public {
        stakingMock = new MockStaking();
        neuronMock = new MockNeuron();

        vm.etch(TARGET_STAKING, address(stakingMock).code);
        vm.etch(TARGET_NEURON, address(neuronMock).code);

        superBurn = new SuperBurn();

        vm.deal(user, 1000 ether);
        vm.deal(TARGET_STAKING, 10000 ether);
    }

    function test_RegisterNeuron_Success_CostZero_RefundsFullAmount() public {
        uint256 amountSent = 1 ether;
        uint256 initialBalance = user.balance;

        vm.expectEmit(true, false, true, true);
        emit NeuronRegistration(netuid, hotkey, user);

        vm.prank(user);
        bool result = superBurn.registerNeuron{value: amountSent}(
            netuid,
            hotkey
        );

        assertTrue(result);
        assertEq(user.balance, initialBalance);
        assertEq(address(superBurn).balance, 0);
    }

    function test_RegisterNeuron_Success_ZeroValue() public {
        uint256 amountSent = 0;
        uint256 initialBalance = user.balance;

        vm.expectEmit(true, false, true, true);
        emit NeuronRegistration(netuid, hotkey, user);

        vm.prank(user);
        bool result = superBurn.registerNeuron{value: amountSent}(
            netuid,
            hotkey
        );

        assertTrue(result);
        assertEq(user.balance, initialBalance);
        assertEq(address(superBurn).balance, 0);
    }

    function testFuzz_RegisterNeuron_RefundsVariousAmounts(uint256 amount) public {
        amount = bound(amount, 1, 500 ether);
        vm.deal(user, amount);

        vm.prank(user);
        superBurn.registerNeuron{value: amount}(netuid, hotkey);

        assertEq(user.balance, amount);
        assertEq(address(superBurn).balance, 0);
    }

    function test_RegisterNeuron_Revert_IfPrecompileFails() public {
        MockNeuron(payable(TARGET_NEURON)).setShouldFail(true);
        uint256 amountToBurn = 1 ether;
        uint256 initialBalance = user.balance;

        vm.prank(user);
        vm.expectRevert(SuperBurn.NeuronRegistrationFailed.selector);

        superBurn.registerNeuron{value: amountToBurn}(
            netuid,
            hotkey
        );

        assertEq(user.balance, initialBalance);
    }

    function test_RegisterNeuron_RefundError_Reverts() public {
        revertingReceiver = new RevertingReceiver();
        vm.deal(address(revertingReceiver), 10 ether);

        uint256 amountSent = 1 ether;

        vm.prank(address(revertingReceiver));
        vm.expectRevert(SuperBurn.RefundError.selector);

        revertingReceiver.callRegister{value: amountSent}(address(superBurn), netuid, hotkey);
    }

    function test_UnstakeAndBurn_Revert_LengthMismatch() public {
        bytes32[] memory hotkeys = new bytes32[](1);
        uint256[] memory amounts = new uint256[](2);

        vm.expectRevert("Length mismatch");
        superBurn.unstakeAndBurn(hotkeys, netuid, amounts);
    }

    function test_UnstakeAndBurn_Revert_RemoveStakeError() public {
        MockStaking(payable(TARGET_STAKING)).setShouldFail(true);

        bytes32[] memory hotkeys = new bytes32[](1);
        uint256[] memory amounts = new uint256[](1);
        hotkeys[0] = hotkey;
        amounts[0] = 1 ether;

        vm.expectRevert(SuperBurn.RemoveStakeError.selector);
        superBurn.unstakeAndBurn(hotkeys, netuid, amounts);
    }

    function test_UnstakeAndBurn_Revert_ReceivedTaoIsZeroError() public {
        bytes32[] memory hotkeys = new bytes32[](1);
        uint256[] memory amounts = new uint256[](1);
        hotkeys[0] = hotkey;
        amounts[0] = 0;

        vm.expectRevert(SuperBurn.ReceivedTaoIsZeroError.selector);
        superBurn.unstakeAndBurn(hotkeys, netuid, amounts);
    }

    function test_UnstakeAndBurn_Success_BurnsCorrectAmount() public {
        bytes32[] memory hotkeys = new bytes32[](1);
        uint256[] memory amounts = new uint256[](1);
        hotkeys[0] = hotkey;
        amounts[0] = 1 ether;

        uint256 initialBurnBalance = TARGET_BURN.balance;

        vm.txGasPrice(1 gwei);
        vm.prank(user);
        superBurn.unstakeAndBurn(hotkeys, netuid, amounts);

        assertTrue(TARGET_BURN.balance > initialBurnBalance);
    }

    function test_UnstakeAndBurn_Success_MultipleInputs() public {
        bytes32[] memory hotkeys = new bytes32[](3);
        uint256[] memory amounts = new uint256[](3);

        hotkeys[0] = bytes32(uint256(1));
        hotkeys[1] = bytes32(uint256(2));
        hotkeys[2] = bytes32(uint256(3));

        amounts[0] = 1 ether;
        amounts[1] = 0.5 ether;
        amounts[2] = 2 ether;

        uint256 initialBurnBalance = TARGET_BURN.balance;
        vm.txGasPrice(1 gwei);

        vm.prank(user);
        superBurn.unstakeAndBurn(hotkeys, netuid, amounts);

        assertTrue(TARGET_BURN.balance > initialBurnBalance);
    }

    function testFuzz_UnstakeAndBurn_VariousAmounts(uint256 amount) public {
        amount = bound(amount, 1000, 1000 ether);

        bytes32[] memory hotkeys = new bytes32[](1);
        uint256[] memory amounts = new uint256[](1);
        hotkeys[0] = hotkey;
        amounts[0] = amount;

        vm.txGasPrice(1 gwei);
        vm.prank(user);
        superBurn.unstakeAndBurn(hotkeys, netuid, amounts);

        assertTrue(TARGET_BURN.balance > 0);
    }

    function test_UnstakeAndBurn_Success_RefundsEverythingIfGasHigh() public {
        bytes32[] memory hotkeys = new bytes32[](1);
        uint256[] memory amounts = new uint256[](1);
        hotkeys[0] = hotkey;
        amounts[0] = 1 ether;

        vm.txGasPrice(1 ether);

        uint256 userBalanceBefore = user.balance;

        vm.prank(user);
        superBurn.unstakeAndBurn(hotkeys, netuid, amounts);

        assertEq(TARGET_BURN.balance, 0);
        assertTrue(user.balance > userBalanceBefore);
    }

    function test_UnstakeAndBurn_Revert_RefundError() public {
        revertingReceiver = new RevertingReceiver();

        bytes32[] memory hotkeys = new bytes32[](1);
        uint256[] memory amounts = new uint256[](1);
        hotkeys[0] = hotkey;
        amounts[0] = 1 ether;

        vm.txGasPrice(1 gwei);

        vm.prank(address(revertingReceiver));
        vm.expectRevert(SuperBurn.RefundError.selector);

        revertingReceiver.callUnstake(address(superBurn), hotkeys, netuid, amounts);
    }

    function test_UnstakeAndBurn_Revert_BurnError() public {
        RevertingReceiver burnReverter = new RevertingReceiver();
        vm.etch(TARGET_BURN, address(burnReverter).code);
        vm.deal(TARGET_BURN, 0);

        bytes32[] memory hotkeys = new bytes32[](1);
        uint256[] memory amounts = new uint256[](1);
        hotkeys[0] = hotkey;
        amounts[0] = 1 ether;

        vm.txGasPrice(0);

        vm.expectRevert(SuperBurn.BurnError.selector);
        superBurn.unstakeAndBurn(hotkeys, netuid, amounts);
    }

    function test_Constants_AreCorrect() public view {
        assertEq(TARGET_BURN, address(0));
        assertEq(TARGET_STAKING, 0x0000000000000000000000000000000000000805);
        assertEq(TARGET_NEURON, 0x0000000000000000000000000000000000000804);
    }
}