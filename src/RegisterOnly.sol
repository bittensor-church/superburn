// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface INeuronPrecompile {
    function burnedRegister(uint16 netuid, bytes32 hotkey) external payable;
}

contract RegisterOnly {
    INeuronPrecompile constant NEURON_PRECOMPILE =
        INeuronPrecompile(0x0000000000000000000000000000000000000804);

    function burnedRegisterNeuron(uint16 netuid, bytes32 hotkey) external payable {
        require(msg.value > 0, "Need TAO to burn");
        NEURON_PRECOMPILE.burnedRegister{value: msg.value}(netuid, hotkey);
    }
}
