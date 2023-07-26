// SPDX-License-Identifier: agpl-3.0
pragma solidity >=0.6.12;

interface IAaveOracle {
  function setAssetSources(address[] calldata assets, address[] calldata sources) external;
  function getAssetPrice(address asset) external view returns (uint256);
  function getSourceOfAsset(address asset) external view returns (address);

}
