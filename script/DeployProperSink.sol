// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import {ProperSink} from "../src/ProperSink.sol";

contract DeployProperSink is Script {
    function run() external {
        // Load deployer private key from environment variable
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(deployerPrivateKey);

        ProperSink properSink = new ProperSink();

        console.log("Deployed ProperSink at:", address(properSink));

        vm.stopBroadcast();
    }
}
