// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.19;

/// @notice Oracle always return 0 for tests
contract NullOracle {
  address public nullToken;
  
  constructor(address token) {
    nullToken = token;
  }
  
  function getAssetPrice(address token) public view returns (uint priceX8){
    if (token != nullToken) priceX8 = 1e8;
  }
}