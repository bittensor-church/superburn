// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import {Sink} from "../src/Sink.sol";

contract DeploySink is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        address deployerAddress = vm.addr(deployerPrivateKey);

        console.log("Starting deployment...");
        console.log("Deployer (Owner) address:", deployerAddress);

        vm.startBroadcast(deployerPrivateKey);

        // 4. Deploy the Sink contract
        // The msg.sender (deployerAddress) will be set as the 'owner' in the constructor
        Sink sink = new Sink();

        vm.stopBroadcast();

        console.log("--------------------------------------------------");
        console.log("Sink contract deployed successfully at:", address(sink));
        console.log("--------------------------------------------------");
    }
}