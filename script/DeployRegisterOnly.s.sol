// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console2} from "forge-std/Script.sol";
import {RegisterOnly} from "../src/RegisterOnly.sol";

contract DeployRegisterOnly is Script {
    function run() external returns (RegisterOnly) {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        RegisterOnly helper = new RegisterOnly();

        console2.log("==== RegisterOnly Deployed ====");
        console2.log("Contract Address:", address(helper));
        console2.log("Neuron Precompile:", "0x0000000000000000000000000000000000000804");
        console2.log("Function: burnedRegisterNeuron(uint16 netuid, bytes32 hotkey, uint256 amountToBurn)");
        console2.log("Usage: prefund contract balance, then call with amountToBurn; contract refunds leftovers.");

        vm.stopBroadcast();
        return helper;
    }
}
