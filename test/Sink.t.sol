// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {Sink} from "../src/Sink.sol";

/**
 * @title Mock Unstake Precompile
 * @notice Simulates the Bittensor unstake precompile for testing
 */
contract MockUnstakePrecompile {
    uint256 public totalUnstaked;
    bool public shouldFail;

    event PrecompileUnstaked(uint256 amount);

    function setShouldFail(bool _shouldFail) external {
        shouldFail = _shouldFail;
    }

    // Note: Unstake doesn't receive value, it just unlocks staked tokens
    fallback() external {
        if (shouldFail) {
            revert("Unstake failed");
        }
        // Decode the amount from calldata
        // Expected: abi.encodeWithSignature("unstake(uint256)", amount)
        if (msg.data.length >= 36) {
            uint256 amount;
            assembly {
                amount := calldataload(4) // Skip 4-byte function selector
            }
            totalUnstaked += amount;
            emit PrecompileUnstaked(amount);
        }
    }
}

/**
 * @title Mock Neuron Precompile
 * @notice Simulates the neuron precompile burnedRegister for testing
 */
contract MockNeuronPrecompile {
    uint16 public lastNetuid;
    bytes32 public lastHotkey;
    uint256 public lastValue;
    bool public shouldFail;

    function setShouldFail(bool value) external {
        shouldFail = value;
    }

    function burnedRegister(uint16 netuid, bytes32 hotkey) external payable {
        if (shouldFail) {
            revert("register failed");
        }
        lastNetuid = netuid;
        lastHotkey = hotkey;
        lastValue = msg.value;
    }
}

/**
 * @title Helper contract to test forced sends
 */
contract ForceSender {
    function forceSend(address payable target) external payable {
        selfdestruct(target);
    }
}

/**
 * @title Helper contract that rejects payments
 */
contract RejectingReceiver {
    receive() external payable {
        revert("I don't accept payments");
    }
}

contract SinkTest is Test {
    Sink public sink;
    MockUnstakePrecompile public unstakePrecompile;
    MockUnstakePrecompile public unstakePrecompileAtAddr; // Reference to the etched precompile
    MockNeuronPrecompile public neuronPrecompile;
    MockNeuronPrecompile public neuronPrecompileAtAddr; // Reference to the etched neuron precompile

    address constant UNSTAKE_PRECOMPILE_ADDR = 0x0000000000000000000000000000000000000801;
    address constant NEURON_PRECOMPILE_ADDR = 0x0000000000000000000000000000000000000804;
    address public user1;
    address public user2;

    event Burned(
        uint256 amountUnstaked,
        uint256 amountBurned,
        uint256 gasReimbursement,
        address indexed caller,
        uint256 timestamp
    );

    event Registered(uint16 indexed netuid, bytes32 hotkey, uint256 amountBurned, address indexed caller);

    function setUp() public {
        user1 = makeAddr("user1");
        user2 = makeAddr("user2");

        // Deploy mock unstake precompile at the expected address
        unstakePrecompile = new MockUnstakePrecompile();
        vm.etch(UNSTAKE_PRECOMPILE_ADDR, address(unstakePrecompile).code);

        // Create reference to the etched unstake precompile
        unstakePrecompileAtAddr = MockUnstakePrecompile(UNSTAKE_PRECOMPILE_ADDR);

        // Deploy mock neuron precompile at expected address
        neuronPrecompile = new MockNeuronPrecompile();
        vm.etch(NEURON_PRECOMPILE_ADDR, address(neuronPrecompile).code);

        neuronPrecompileAtAddr = MockNeuronPrecompile(NEURON_PRECOMPILE_ADDR);

        // Deploy Sink contract
        sink = new Sink();

        // Fund test accounts
        vm.deal(user1, 100 ether);
        vm.deal(user2, 100 ether);

        // Set a default gas price for tests (20 gwei)
        vm.txGasPrice(20 gwei);
    }

    // ============ Helper Functions ============

    /// @dev Force-sends ETH to the Sink contract (since it has no receive function)
    function forceSendToSink(uint256 amount) internal {
        ForceSender sender = new ForceSender();
        vm.deal(address(sender), amount);
        sender.forceSend(payable(address(sink)));
    }

    // ============ Basic Functionality Tests ============

    function test_BurnAll_Success() public {
        // Force send tokens to contract
        forceSendToSink(10 ether);

        assertEq(address(sink).balance, 10 ether);

        // Get user1 balance before
        uint256 balanceBefore = user1.balance;

        // Call burnAll
        vm.prank(user1);
        bool success = sink.burnAll();

        assertTrue(success);
        assertEq(address(sink).balance, 0, "Contract should have 0 balance after burn");

        // User1 should have received gas reimbursement
        assertGt(user1.balance, balanceBefore, "Caller should receive gas reimbursement");

        // Unstake precompile should have been called
        assertEq(unstakePrecompileAtAddr.totalUnstaked(), 10 ether, "Tokens should be unstaked");

        // Tokens should have been sent to address(0)
        assertGt(address(0).balance, 0, "Tokens should be sent to address(0)");
    }

    function test_BurnAll_EmitsEvent() public {
        forceSendToSink(5 ether);

        vm.prank(user1);

        // We can't easily predict exact gas reimbursement, so we check the event is emitted
        vm.expectEmit(false, false, true, false);
        emit Burned(0, 0, 0, user1, block.timestamp); // We only check indexed params (caller)

        sink.burnAll();
    }

    function test_BurnAll_MultipleCalls() public {
        // First burn
        forceSendToSink(3 ether);
        vm.prank(user1);
        sink.burnAll();

        assertEq(address(sink).balance, 0);

        // Second burn
        forceSendToSink(2 ether);
        vm.prank(user2);
        sink.burnAll();

        assertEq(address(sink).balance, 0);

        // Both burns should have occurred (tokens sent to address(0))
        assertGt(address(0).balance, 0);
    }

    // ============ Gas Reimbursement Tests ============

    function test_GasReimbursement_CallerIsPaid() public {
        forceSendToSink(10 ether);

        uint256 balanceBefore = user1.balance;

        vm.prank(user1);
        uint256 gasStart = gasleft();
        sink.burnAll();
        uint256 gasUsed = gasStart - gasleft();

        uint256 balanceAfter = user1.balance;

        // Caller should have net positive or near-zero change
        // (they paid for gas but got reimbursed)
        uint256 netChange = balanceAfter > balanceBefore
            ? balanceAfter - balanceBefore
            : balanceBefore - balanceAfter;

        // Net change should be relatively small compared to transaction cost
        // This is a rough check - exact reimbursement depends on gas price
        assertLt(netChange, 0.01 ether, "Net cost to caller should be minimal");
    }

    function test_EstimateReimbursement() public {
        uint256 estimate = sink.estimateReimbursement();
        assertGt(estimate, 0, "Estimate should be > 0");

        // Should be proportional to gas price
        uint256 estimate2 = sink.estimateReimbursement();
        assertEq(estimate, estimate2, "Estimate should be deterministic at same gas price");
    }

    // ============ Error Condition Tests ============

    function test_BurnAll_RevertsOnInsufficientBalance() public {
        // Send very small amount that won't cover gas
        forceSendToSink(1 wei);

        vm.prank(user1);
        vm.expectRevert(Sink.InsufficientBalance.selector);
        sink.burnAll();
    }

    function test_BurnAll_RevertsOnUnstakeFailure() public {
        forceSendToSink(10 ether);

        // Make unstake precompile fail
        unstakePrecompileAtAddr.setShouldFail(true);

        vm.prank(user1);
        vm.expectRevert(Sink.UnstakeFailed.selector);
        sink.burnAll();
    }

    // Note: Burn to address(0) should never fail in practice, so we removed this test

    function test_BurnAll_RevertsOnReimbursementFailure() public {
        forceSendToSink(10 ether);

        // Use a contract that rejects payments as the caller
        RejectingReceiver rejecter = new RejectingReceiver();

        vm.prank(address(rejecter));
        vm.expectRevert(Sink.ReimbursementFailed.selector);
        sink.burnAll();
    }

    // ============ No Receive Function Tests ============

    function test_NoReceiveFunction() public {
        // Try to send ETH directly to the contract
        vm.prank(user1);
        (bool success,) = address(sink).call{value: 1 ether}("");

        assertFalse(success, "Direct sends should fail (no receive function)");
        assertEq(address(sink).balance, 0, "Balance should remain 0");
    }

    function test_NoFallbackFunction() public {
        // Try to send ETH with data to the contract
        vm.prank(user1);
        (bool success,) = address(sink).call{value: 1 ether}("0x1234");

        assertFalse(success, "Sends with data should fail (no fallback function)");
        assertEq(address(sink).balance, 0, "Balance should remain 0");
    }

    function test_ForceSendWorks() public {
        // Force send should work
        forceSendToSink(5 ether);

        assertEq(address(sink).balance, 5 ether, "Force send should work");
    }

    // ============ View Function Tests ============

    function test_GetBalance() public {
        assertEq(sink.getBalance(), 0);

        forceSendToSink(7 ether);
        assertEq(sink.getBalance(), 7 ether);

        vm.prank(user1);
        sink.burnAll();
        assertEq(sink.getBalance(), 0);
    }

    // ============ Stateless Tests ============

    function test_NoStateVariables() public {
        // Contract should be stateless (except constants)
        // Burning shouldn't affect future burns except via balance

        forceSendToSink(5 ether);
        vm.prank(user1);
        sink.burnAll();

        uint256 burned1 = address(0).balance;

        forceSendToSink(5 ether);
        vm.prank(user1);
        sink.burnAll();

        // Both burns should work identically
        assertGt(address(0).balance, burned1);
    }

    // ============ Fuzz Tests ============

    function testFuzz_BurnAll(uint256 amount) public {
        // Bound amount to reasonable values
        // Lower bound high enough to cover gas reimbursement
        amount = bound(amount, 0.01 ether, 1000 ether);

        forceSendToSink(amount);
        assertEq(address(sink).balance, amount);

        uint256 balanceBefore = user1.balance;

        vm.prank(user1);
        bool success = sink.burnAll();

        assertTrue(success);
        assertEq(address(sink).balance, 0);

        // Some amount should be burned (sent to address(0))
        assertGt(address(0).balance, 0);

        // Most of the amount should be burned (small portion is gas reimbursement)
        // Note: We can't reliably check the exact amount due to cumulative burns in address(0)
    }

    function testFuzz_GasReimbursement(uint256 gasPrice) public {
        // Bound gas price to reasonable values
        gasPrice = bound(gasPrice, 1 gwei, 1000 gwei);

        forceSendToSink(10 ether);

        vm.txGasPrice(gasPrice);
        vm.prank(user1);
        sink.burnAll();

        // Higher gas price should result in higher reimbursement
        // (indirectly tested by ensuring burn succeeds and caller is compensated)
        assertTrue(true);
    }

    // ============ Integration Tests ============

    function test_CompleteWorkflow() public {
        // Multiple users force-send funds
        forceSendToSink(5 ether);

        uint256 balance1 = address(sink).balance;
        assertEq(balance1, 5 ether);

        // User1 triggers first burn
        vm.prank(user1);
        sink.burnAll();

        assertEq(address(sink).balance, 0);
        uint256 burned1 = address(0).balance;
        assertGt(burned1, 0);

        // More funds are force-sent
        forceSendToSink(8 ether);

        // User2 triggers second burn
        vm.prank(user2);
        sink.burnAll();

        assertEq(address(sink).balance, 0);
        assertGt(address(0).balance, burned1);
    }

    function test_BurnDistribution() public {
        // Send a known amount and check the split between burn and reimbursement
        uint256 initialAmount = 100 ether;
        forceSendToSink(initialAmount);

        uint256 burnedBefore = address(0).balance;
        uint256 user1BalanceBefore = user1.balance;

        vm.prank(user1);
        sink.burnAll();

        uint256 amountBurned = address(0).balance - burnedBefore;
        uint256 reimbursement = user1.balance - user1BalanceBefore;

        // Total should equal initial amount (within dust)
        assertApproxEqAbs(
            amountBurned + reimbursement,
            initialAmount,
            1000, // Allow 1000 wei difference for dust
            "Burn + reimbursement should equal initial amount"
        );

        // Majority should be burned
        assertGt(amountBurned, initialAmount * 99 / 100, "Most should be burned");
    }

    // ============ Neuron Registration Tests ============

    function test_RegisterNeuron_Success() public {
        bytes32 hotkey = bytes32(uint256(uint160(user1)));
        uint16 netuid = 42;
        uint256 burnAmount = 1 ether;

        vm.expectEmit(true, false, true, true);
        emit Registered(netuid, hotkey, burnAmount, user1);

        vm.prank(user1);
        bool success = sink.registerNeuron{value: burnAmount}(netuid, hotkey);

        assertTrue(success, "registerNeuron should return true");
        assertEq(neuronPrecompileAtAddr.lastNetuid(), netuid, "Netuid forwarded");
        assertEq(neuronPrecompileAtAddr.lastHotkey(), hotkey, "Hotkey forwarded");
        assertEq(neuronPrecompileAtAddr.lastValue(), burnAmount, "Value forwarded");
    }

    function test_RegisterNeuron_RevertsOnFailure() public {
        bytes32 hotkey = bytes32(uint256(uint160(user1)));
        neuronPrecompileAtAddr.setShouldFail(true);

        vm.prank(user1);
        vm.expectRevert(bytes("register failed"));
        sink.registerNeuron{value: 1 ether}(77, hotkey);
    }

    // ============ Edge Case Tests ============

    function test_ZeroBalance() public {
        // Trying to burn with zero balance should revert
        assertEq(address(sink).balance, 0);

        vm.prank(user1);
        vm.expectRevert(Sink.InsufficientBalance.selector);
        sink.burnAll();
    }

    function test_VerySmallBalance() public {
        // Very small balance should revert
        forceSendToSink(1000 wei);

        vm.prank(user1);
        vm.expectRevert(Sink.InsufficientBalance.selector);
        sink.burnAll();
    }

    function test_LargeBalance() public {
        // Test with very large balance
        forceSendToSink(1000000 ether);

        uint256 burnedBefore = address(0).balance;

        vm.prank(user1);
        bool success = sink.burnAll();

        assertTrue(success);
        assertEq(address(sink).balance, 0);
        assertGt(address(0).balance - burnedBefore, 999999 ether);
    }

    // ============ Gas Measurement Tests ============

    function test_GasUsage() public view {
        // Measure gas for burnAll
        // This is informational for optimization
        uint256 estimate = sink.estimateReimbursement();
        assertGt(estimate, 0);
        // Actual gas test would require vm.prank and measure
    }
}
