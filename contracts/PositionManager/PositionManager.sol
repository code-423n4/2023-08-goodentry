// SPDX-License-Identifier: none
pragma solidity 0.8.19;
import "../openzeppelin-solidity/contracts/token/ERC20/ERC20.sol";
import "../openzeppelin-solidity/contracts/token/ERC20/utils/SafeERC20.sol";

import {IFlashLoanReceiver} from "../../interfaces/IFlashLoanReceiver.sol";
import {ILendingPoolAddressesProvider} from "../../interfaces/ILendingPoolAddressesProvider.sol";
import {ILendingPool} from "../../interfaces/IAaveLendingPoolV2.sol";
import {IPriceOracle} from "../../interfaces/IPriceOracle.sol";
import "../../interfaces/IUniswapV2Router01.sol";
import "../../interfaces/IUniswapV2Pair.sol";
import "../../interfaces/IUniswapV2Factory.sol";

import "../RoeRouter.sol";


contract PositionManager is IFlashLoanReceiver {
  using SafeERC20 for ERC20;

  ////////////////////// VARS
  ILendingPoolAddressesProvider public ADDRESSES_PROVIDER; // IFlashLoanReceiver  requirement
  ILendingPool public LENDING_POOL; // IFlashLoanReceiver  requirement
  RoeRouter public ROEROUTER; 
  
  
  ////////////////////// GENERAL   

  /// @param roerouter Address of Roe whitelist router
  constructor(address roerouter) {
    require(roerouter != address(0x0), "Invalid address");
    ROEROUTER = RoeRouter(roerouter);
  }


  ////////////////////// DISPATCHER
  
  /**
   * @notice Aave-compatible flashloan receiver
   * @param assets The address of the flash-borrowed asset
   * @param amounts The amount of the flash-borrowed asset
   * @param premiums The fee of the flash-borrowed asset
   * @param initiator The address of the flashloan initiator
   * @param params The byte-encoded params passed when initiating the flashloan
   * @return result True if the execution of the operation succeeds, false otherwise
   */
  function executeOperation(
    address[] calldata assets,
    uint256[] calldata amounts,
    uint256[] calldata premiums,
    address initiator,
    bytes calldata params
  ) virtual external returns (bool result) {
  }
  
  
  /// @notice Get lp, oracle, router and underlying tokens from RoeRouter
  /// @param poolId Id of the ROE pool
  /// @return lp ROE Lending pool address
  /// @return oracle Lending pool oracle
  /// @return router Lending pool LP asset router
  /// @return token0 First underlying token in lexicographic order
  /// @return token1 Second underlying token
  function getPoolAddresses(uint poolId) 
    internal view 
    returns( ILendingPool lp, IPriceOracle oracle, IUniswapV2Router01 router, address token0, address token1) 
  {
    (address lpap, address _token0, address _token1, address r, ) = ROEROUTER.pools(poolId);
    token0 = _token0;
    token1 = _token1;
    lp = ILendingPool(ILendingPoolAddressesProvider(lpap).getLendingPool());
    oracle = IPriceOracle(ILendingPoolAddressesProvider(lpap).getPriceOracle());
    router = IUniswapV2Router01(r);
  }
  
  
  /// @notice Check and set allowance
  /// @param token Token address
  /// @param spender Spender address
  /// @param amount Minimum allowance needed
  function checkSetAllowance(address token, address spender, uint amount) internal {
    if ( ERC20(token).allowance(address(this), spender) < amount ) ERC20(token).safeIncreaseAllowance(spender, type(uint256).max);
  }
  
  
  /// @notice Deposit remaining users assets back to ROE, repaying debt if any
  /// @param LP The ROE lending pool
  /// @param user The owner of the tokens
  /// @param asset The first asset to deposit
  function cleanup(ILendingPool LP, address user, address asset) internal {
    uint amt = ERC20(asset).balanceOf(address(this));
    if (amt > 0) {
      checkSetAllowance(asset, address(LP), amt);
      
      // if there is a debt, try to repay the debt 
      uint debt = ERC20(LP.getReserveData(asset).variableDebtTokenAddress).balanceOf(user);
      if ( debt > 0 ){
        if (amt <= debt ) {
          LP.repay( asset, amt, 2, user);
          return;
        }
        else {
          LP.repay( asset, debt, 2, user);
          amt = amt - debt;
        }
      }
      // deposit remaining tokens
      LP.deposit( asset, amt, user, 0 );
    }
  }


  /// @notice Send dust to treasury
  /// @param asset The token to transfer
  function removeDust(address asset) external {
    ERC20(asset).safeTransfer(ROEROUTER.treasury(), ERC20(asset).balanceOf(address(this))); 
  }


  /// @notice Transfer amount of aAssets here and withdraw without checks
  /// @param LP The ROE lending pool
  /// @param user The owner of the tokens withdrawn
  /// @param asset The asset withdrawn
  /// @param amount The amount withdrawn
  function PMWithdraw(ILendingPool LP, address user, address asset, uint amount) internal {
    if ( amount > 0 ){
      LP.PMTransfer(LP.getReserveData(asset).aTokenAddress, user, amount);
      LP.withdraw(asset, amount, address(this));
    }
  }  
  
  
  /// @notice Check LP underlying assets value against oracle values: allow a 1% error
  /// @param oracle The Lending pool oracle for the LP token
  /// @param assetA The first token address
  /// @param amountA The first token amount
  /// @param assetB The second token address
  /// @param amountB The second token amount
  function validateValuesAgainstOracle(IPriceOracle oracle, address assetA, uint amountA, address assetB, uint amountB) internal view {
    uint decimalsA = ERC20(assetA).decimals();
    uint decimalsB = ERC20(assetB).decimals();
    uint valueA = amountA * oracle.getAssetPrice(assetA);
    uint valueB = amountB * oracle.getAssetPrice(assetB);
    if (decimalsA > decimalsB) valueA = valueA / 10 ** (decimalsA - decimalsB);
    else if (decimalsA < decimalsB) valueB = valueB / 10 ** (decimalsB - decimalsA);
    require( valueA <= valueB * 101 / 100, "PM: LP Oracle Error");
    require( valueB <= valueA * 101 / 100, "PM: LP Oracle Error");
  }
}
