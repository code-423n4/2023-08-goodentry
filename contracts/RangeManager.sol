// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "./openzeppelin-solidity/contracts/token/ERC20/ERC20.sol";
import "./openzeppelin-solidity/contracts/token/ERC20/utils/SafeERC20.sol";
import "./openzeppelin-solidity/contracts/utils/cryptography/ECDSA.sol";
import "./openzeppelin-solidity/contracts/token/ERC20/utils/SafeERC20.sol";
import "./openzeppelin-solidity/contracts/security/ReentrancyGuard.sol";
import "../interfaces/AggregatorV3Interface.sol";
import "../interfaces/ILendingPoolAddressesProvider.sol";
import "../interfaces/IAaveLendingPoolV2.sol";
import "../interfaces/IAaveOracle.sol";
import "../interfaces/IUniswapV2Pair.sol";
import "../interfaces/IUniswapV2Factory.sol";
import "../interfaces/IUniswapV2Router01.sol";
import "../interfaces/ISwapRouter.sol";
import "../interfaces/INonfungiblePositionManager.sol";
import "./TokenisableRange.sol";
import "./openzeppelin-solidity/contracts/proxy/beacon/BeaconProxy.sol";
import "./openzeppelin-solidity/contracts/access/Ownable.sol";
import {IPriceOracle} from "../interfaces/IPriceOracle.sol";


/// @title Range middleware between ROE lending pool and various ranges
contract RangeManager is ReentrancyGuard, Ownable {
  using SafeERC20 for ERC20;
  ILendingPool public LENDING_POOL;
  event Withdraw(address user, address asset, uint amount);
  event Deposit(address user, address asset, uint amount);
  event AddRange(uint128 startX10, uint128 endX10, uint step);

  ERC20 public ASSET_0;
  ERC20 public ASSET_1;

  // Constant across chains - https://docs.uniswap.org/protocol/reference/deployments
  INonfungiblePositionManager constant public POS_MGR = INonfungiblePositionManager(0xC36442b4a4522E871399CD717aBDD847Ab11FE88);  

  struct Step {
    uint128 start;
    uint128 end;
  }

  Step [] public stepList; 
  TokenisableRange [] public tokenisedRanges;
  TokenisableRange [] public tokenisedTicker;
  
  
  constructor(ILendingPool lendingPool, ERC20 _asset0, ERC20 _asset1)  {
    require( address(lendingPool) != address(0x0), "Invalid address" );
    LENDING_POOL = lendingPool;
    ASSET_0 = _asset0 < _asset1 ? _asset0 : _asset1;
    ASSET_1 = _asset0 < _asset1 ? _asset1 : _asset0;
  }


  /// @notice Checks validity and non overlap of the price ranges
  /// @param start range low price bound
  /// @param end range high price bound
  function checkNewRange(uint128 start, uint128 end) internal view {
    require(start < end, "Range invalid");
    uint256 len = stepList.length;
    for (uint i = 0; i < len; i++) {
      if (start >= stepList[i].end || end <= stepList[i].start) {
        continue;
      }
      revert("Range overlap");
    } 
  }
  
  /// @notice Generate Ticker and Ranger ranges
  /// @param startX10 Range lower price scaled by 1e10
  /// @param endX10 Range high price scaled by 1e10
  /// @param startName Name of the range lower bound 
  /// @param endName Name of the range higher bound
  function generateRange(uint128 startX10, uint128 endX10, string memory startName, string memory endName, address beacon) external onlyOwner {
    require(beacon != address(0x0), "Invalid beacon");
    checkNewRange(startX10, endX10);
    stepList.push( Step(startX10, endX10) );
    BeaconProxy trbp = new BeaconProxy(beacon, "");
    tokenisedRanges.push( TokenisableRange(address(trbp)) );
    trbp = new BeaconProxy(beacon, "");
    tokenisedTicker.push( TokenisableRange(address(trbp)) );
    IAaveOracle oracle = IAaveOracle(ILendingPoolAddressesProvider( LENDING_POOL.getAddressesProvider() ).getPriceOracle());
    
    tokenisedRanges[ tokenisedRanges.length - 1 ].initProxy(oracle, ASSET_0, ASSET_1, startX10, endX10, startName, endName, false);
    tokenisedTicker[ tokenisedTicker.length - 1 ].initProxy(oracle, ASSET_0, ASSET_1, startX10, endX10, startName, endName, true); 
    emit AddRange(startX10, endX10, tokenisedRanges.length - 1);
  }
  
  
  /// @notice Initialize a previously created ticker
  /// @param tr Range address
  /// @param amount0 Amount of token0
  /// @param amount1 Amount of token1
  function initRange(address tr, uint amount0, uint amount1) external onlyOwner {
    ASSET_0.safeTransferFrom(msg.sender, address(this), amount0);
    ASSET_0.safeIncreaseAllowance(tr, amount0);
    ASSET_1.safeTransferFrom(msg.sender, address(this), amount1);
    ASSET_1.safeIncreaseAllowance(tr, amount1);
    TokenisableRange(tr).init(amount0, amount1);
    ERC20(tr).safeTransfer(msg.sender, TokenisableRange(tr).balanceOf(address(this)));
  }


  /// @notice Remove assets from tokenisedRanges
  /// @param step Id of the range+ticker step from which to remove assets
  function removeFromStep(uint256 step) internal {
    require(step < tokenisedRanges.length && step < tokenisedTicker.length, "Invalid step");
    uint256 trAmt;
    
    trAmt = ERC20(LENDING_POOL.getReserveData(address(tokenisedRanges[step])).aTokenAddress).balanceOf(msg.sender);   
    if (trAmt > 0) {       
        LENDING_POOL.PMTransfer(
          LENDING_POOL.getReserveData(address(tokenisedRanges[step])).aTokenAddress, 
          msg.sender, 
          trAmt
        );
        trAmt = LENDING_POOL.withdraw(address(tokenisedRanges[step]), type(uint256).max, address(this));
        tokenisedRanges[step].withdraw(trAmt, 0, 0);
        emit Withdraw(msg.sender, address(tokenisedRanges[step]), trAmt);
    }        

    trAmt = ERC20(LENDING_POOL.getReserveData(address(tokenisedTicker[step])).aTokenAddress).balanceOf(msg.sender);
    if (trAmt > 0) {    
        LENDING_POOL.PMTransfer(
          LENDING_POOL.getReserveData(address(tokenisedTicker[step])).aTokenAddress, 
          msg.sender, 
          trAmt
        );
        uint256 ttAmt = LENDING_POOL.withdraw(address(tokenisedTicker[step]), type(uint256).max, address(this));
        tokenisedTicker[step].withdraw(ttAmt, 0, 0);
        emit Withdraw(msg.sender, address(tokenisedTicker[step]), trAmt);
    }           
  }


  /// @notice Remove assets from tokenisedRanges
  /// @param step Id of the range+ticker step from which to remove assets
  function removeAssetsFromStep(uint256 step) nonReentrant external {
    removeFromStep(step);
    cleanup();
  }
  
  
  /// @notice Transfer assets from the lending pool to a tokenizedRange
  /// @param tr TokenisableRange instance into which to transfer assets
  /// @param step Id of the range+ticker step from which to remove assets
  /// @param amount0 Amount of asset0 to transfer in the TR
  /// @param amount1 Amount of asset1 to transfer in the TR
  /// @dev Useful to remove from a previous range and deposit into a new TR when price moves
  function transferAssetsIntoStep(TokenisableRange tr, uint256 step, uint256 amount0, uint256 amount1) internal {
    removeFromStep(step);
    if (amount0 > 0) {    
      LENDING_POOL.PMTransfer( LENDING_POOL.getReserveData(address(ASSET_0)).aTokenAddress, msg.sender, amount0 );
      LENDING_POOL.withdraw( address(ASSET_0), amount0, address(this) );
      ASSET_0.safeIncreaseAllowance(address(tr), amount0);
    }
    if (amount1 > 0) {
      LENDING_POOL.PMTransfer( LENDING_POOL.getReserveData(address(ASSET_1)).aTokenAddress, msg.sender, amount1 );
      LENDING_POOL.withdraw( address(ASSET_1), amount1, address(this) );
      ASSET_1.safeIncreaseAllowance(address(tr), amount1);
    }
    uint256 lpAmt = tr.deposit(amount0, amount1);
    emit Deposit(msg.sender, address(tr), lpAmt);
    tr.approve(address(LENDING_POOL), lpAmt);
    LENDING_POOL.deposit(address(tr), lpAmt, msg.sender, 0);
    cleanup();
  }


  /// @notice Transfer assets from the lending pool to a Ranger
  /// @param step Id of the range+ticker step from which to remove assets
  /// @param amount0 Amount of asset0 to transfer in the Range
  /// @param amount1 Amount of asset1 to transfer in the Range
  function transferAssetsIntoRangerStep(uint256 step, uint256 amount0, uint256 amount1) nonReentrant external {
    transferAssetsIntoStep(tokenisedRanges[step], step, amount0, amount1);
  }


  /// @notice Transfer assets from the lending pool to a Ticker
  /// @param step Id of the range+ticker step from which to remove assets
  /// @param amount0 Amount of asset0 to transfer in the Ticker
  /// @param amount1 Amount of asset1 to transfer in the Ticker
  function transferAssetsIntoTickerStep(uint256 step, uint256 amount0, uint256 amount1) nonReentrant external {
    transferAssetsIntoStep(tokenisedTicker[step], step, amount0, amount1);
  }


  /// @notice Check token balances and return assets to the user
  function cleanup() internal {
    uint256 asset0_amt = ASSET_0.balanceOf(address(this));
    uint256 asset1_amt = ASSET_1.balanceOf(address(this));
    
    if (asset0_amt > 0) {
      ASSET_0.safeIncreaseAllowance(address(LENDING_POOL), asset0_amt);
      LENDING_POOL.deposit(address(ASSET_0), asset0_amt, msg.sender, 0);
    }
    
    if (asset1_amt > 0) {
      ASSET_1.safeIncreaseAllowance(address(LENDING_POOL), asset1_amt);
      LENDING_POOL.deposit(address(ASSET_1), asset1_amt, msg.sender, 0);
    }
    
    // Check that health factor is not put into liquidation / with buffer
    (,,,,,uint256 hf) = LENDING_POOL.getUserAccountData(msg.sender);
    require(hf > 1.01e18, "Health factor is too low");
  }


  /// @notice Get length of stepList
  /// @return listLength Length
  function getStepListLength() external view returns (uint256 listLength) {
    listLength = stepList.length;
  }
}
