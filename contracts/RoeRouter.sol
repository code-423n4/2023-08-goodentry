// SPDX-License-Identifier: none
pragma solidity 0.8.19;

import "./openzeppelin-solidity/contracts/access/Ownable.sol";


/**
 * Contract RoeRouter holds a list of whitelisted ROE lending pools and important parameters
 */
contract RoeRouter is Ownable {
  /// EVENTS
  event AddPool(uint poolId, address lendingPoolAddressProvider);
  event DeprecatePool(uint poolId);
  event UpdateTreasury(address treasury);

  /// ROE treasury
  address public treasury;

  /// List of pools
  RoePool[] public pools;

  /// Lending pool structure
  struct RoePool {
    address lendingPoolAddressProvider;
    address token0;
    address token1;
    address ammRouter;
    bool isDeprecated;
  }
  
  
  /// @notice constructor
  constructor (address treasury_) {
    require(treasury_ != address(0x0), "Invalid address");
    treasury = treasury_;
  }
  
  
  /// @notice Return pool list length
  function getPoolsLength() public view returns (uint poolLength) {
    poolLength = pools.length;
  }
  
  
  /// @notice Deprecate a pool
  /// @param poolId pool ID
  /// @dev isDeprecated is a statement about the pool record, and does not imply anything about the pool itself
  function deprecatePool(uint poolId) public onlyOwner {
    pools[poolId].isDeprecated = true;
    emit DeprecatePool(poolId);
  }
  
  
  /// @notice Add a new pool parameters
  /// @param lendingPoolAddressProvider address of a ROE Aave-compatible lending pool address provider
  /// @param token0 address of the one token of the pair 
  /// @param token1 address of the second token of the pair
  /// @param ammRouter address of the AMMv2 such that the LP pair ammRouter.factory.getPair(token0, token1) is supported by the lending pool
  function addPool(
    address lendingPoolAddressProvider, 
    address token0, 
    address token1, 
    address ammRouter
  ) 
    public onlyOwner 
    returns (uint poolId)
  {
    require (
      lendingPoolAddressProvider != address(0x0) 
      && token0 != address(0x0) 
      && token1 != address(0x0) 
      && ammRouter != address(0x0), 
      "Invalid Address"
    );
    require(token0 < token1, "Invalid Order");
    pools.push(RoePool(lendingPoolAddressProvider, token0, token1, ammRouter, false));
    poolId = pools.length - 1;
    emit AddPool(poolId, lendingPoolAddressProvider);
  }
  
  /// @notice Modify treaury address
  /// @param newTreasury New treasury address
  function setTreasury(address newTreasury) public onlyOwner {
    require(newTreasury != address(0x0), "Invalid address");
    treasury = newTreasury;
    emit UpdateTreasury(newTreasury);
  }
}