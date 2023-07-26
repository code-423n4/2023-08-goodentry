// SPDX-License-Identifier: none
pragma solidity 0.8.19;

import "./PositionManager.sol";
import "../TokenisableRange.sol";

interface  AmountsRouter {
  function getAmountsOut(uint256 amountIn, address[] calldata path) external returns (uint256[] memory amounts);
  function getAmountsIn(uint256 amountOut, address[] calldata path) external returns (uint256[] memory amounts);
}

contract OptionsPositionManager is PositionManager {
  using SafeERC20 for IERC20;

  ////////////////////// EVENTS
  event BuyOptions(address indexed user, address indexed asset, uint amount, uint amount0, uint amount1);
  event SellOptions(address indexed user, address indexed asset, uint amount, uint amount0, uint amount1);
  event ClosePosition(address indexed user, address indexed asset, uint amount, uint amount0, uint amount1);
  event LiquidatePosition(address indexed user, address indexed asset, uint amount, uint amount0, uint amount1);
  event ReducedPosition(address indexed user, address indexed asset, uint amount);
  event Swap(address indexed user, address sourceAsset, uint sourceAmount, address targetAsset, uint targetAmount);


  /// @param roerouter Address of Roe whitelist router
  constructor (address roerouter) PositionManager(roerouter) {}


  ////////////////////// DISPATCHER
  /**
   * @notice Aave-compatible flashloan receiver dispatch: open a leverage position or liquidate a position
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
  ) override external returns (bool result) {
    uint8 mode = abi.decode(params, (uint8) );
    // Buy options
    if ( mode == 0 ){
      (, uint poolId, address user, address[] memory sourceSwap) = abi.decode(params, (uint8, uint, address, address[]));
      executeBuyOptions(poolId, assets, amounts, user, sourceSwap);
    }
    // Liquidate
    else {
      (, uint poolId, address user, address collateral) = abi.decode(params, (uint8, uint, address, address));
      executeLiquidation(poolId, assets, amounts, user, collateral);
    }
    result = true;
  }
  
  
  /// @notice Buy each flashloaned option
  function executeBuyOptions(
    uint poolId,
    address[] calldata assets,
    uint256[] calldata amounts,
    address user,
    address[] memory sourceSwap
  ) internal {
    (ILendingPool lendingPool,,, address token0, address token1 ) = getPoolAddresses(poolId);
    require( address(lendingPool) == msg.sender, "OPM: Call Unallowed");
    
    for ( uint8 k = 0; k<assets.length; k++){
      address asset = assets[k];
      uint amount = amounts[k];
      withdrawOptionAssets(poolId, asset, amount, sourceSwap[k], user);
    }
    // send all tokens to lendingPool
    cleanup(lendingPool, user, token0);
    cleanup(lendingPool, user, token1);
  }
  
  
  /// @notice Execute operation liquidation
  function executeLiquidation(
    uint poolId,
    address[] calldata assets,
    uint256[] calldata amounts,
    address user,
    address collateral
  ) internal {
    (ILendingPool lendingPool,,, address token0, address token1) = getPoolAddresses(poolId);
    require( address(lendingPool) == msg.sender, "OPM: Call Unallowed");
    uint[2] memory amts = [ERC20(token0).balanceOf(address(this)), ERC20(token1).balanceOf(address(this))];
    for ( uint8 k =0; k<assets.length; k++){
      address debtAsset = assets[k];
      
      // simple liquidation: debt is transferred from user to liquidator and collateral deposited to roe
      uint amount = amounts[k];
      
      // liquidate and send assets here
      checkSetAllowance(debtAsset, address(lendingPool), amount);
      lendingPool.liquidationCall(collateral, debtAsset, user, amount, false);
      // repay tokens
      uint debt = closeDebt(poolId, address(this), debtAsset, amount, collateral);
      uint amt0 = ERC20(token0).balanceOf(address(this));
      uint amt1 = ERC20(token1).balanceOf(address(this));
      emit LiquidatePosition(user, debtAsset, debt, amt0 - amts[0], amt1 - amts[1]);
      amts[0] = amt0;
      amts[1] = amt1;
      
    }
  }


  ////////////////////// BUY OPTIONS
  
  /// @notice Withdraw underlying option assets and swap if necessary
  /// @param poolId ID of the ROE lending pool
  /// @param flashAsset Option asset to borrow
  /// @param flashAmount Amount to borrow
  /// @param sourceSwap Asset to swap (put-call parity)
  /// @param user Address of option buyer
  /// @dev Only withdraws the tokens and swap, doesnt deposit, as this is done afterwards to avoid doing multiple times
  function withdrawOptionAssets(
    uint poolId,
    address flashAsset,
    uint256 flashAmount,
    address sourceSwap,
    address user
  ) 
    private returns (bool result)
  {
    (, IPriceOracle oracle, IUniswapV2Router01 router, address token0, address token1) = getPoolAddresses(poolId);
    sanityCheckUnderlying(flashAsset, token0, token1);
    // Remove Liquidity and get underlying tokens
    (uint256 amount0, uint256 amount1) = TokenisableRange(flashAsset).withdraw(flashAmount, 0, 0);
    if (sourceSwap != address(0) ){
      require(sourceSwap == token0 || sourceSwap == token1, "OPM: Invalid Swap Token");
      address[] memory path = new address[](2);
      path[0] = sourceSwap ;
      path[1] = sourceSwap == token0 ? token1 : token0;
      uint amount = sourceSwap == token0 ? amount0 : amount1;

      uint received = swapExactTokensForTokens(router, oracle, amount, path);
      // if swap underlying, then sourceSwap amount is 0 and the other amount is amount withdrawn + amount received from swap
      amount0 = sourceSwap == token0 ? 0 : amount0 + received;
      amount1 = sourceSwap == token1 ? 0 : amount1 + received;
    }
    emit BuyOptions(user, flashAsset, flashAmount, amount0, amount1);
    result = true;
  }

  
  /// @notice Buy a list of option. An option is a triplet [TRAddress, amount, putOrCall]
  /// @param poolId ID of the ROE lending pool
  /// @param options Option addresses list
  /// @param amounts Option amounts list
  /// @param sourceSwap Source swap address for call-put parity
  /// @dev Because tickers are one coin or the other depending on the price, one can only buy OTM options. You can get ITM put by buying OTM call and swapping, or get ITM call by buying OTM put and swapping. If you wanna swap, set sourceSwap to the asset you *dont* want, otherwise must be address(0x0)
  function buyOptions(
    uint poolId, 
    address[] memory options, 
    uint[] memory amounts, 
    address[] memory sourceSwap
  )
    external
  {
    require(options.length == amounts.length && sourceSwap.length == options.length, "OPM: Array Length Mismatch");
    bytes memory params = abi.encode(0, poolId, msg.sender, sourceSwap);
    (ILendingPool LP,,,, ) = getPoolAddresses(poolId);

    uint[] memory flashtype = new uint[](options.length);
    for (uint8 i = 0; i< options.length; ){
      flashtype[i] = 2;
      unchecked { i+=1; }
    }
    LP.flashLoan( address(this), options, amounts, flashtype, msg.sender, params, 0);
  }

  
  ////////////////////// LIQUIDATIONS
  
  /// @notice Liquidate up to 50% of an unhealthy position
  /// @param poolId ID of the ROE lending pool
  /// @param user The owner of the loan to liquidate
  /// @param options Array of borrowed Ticker assets to repay
  /// @param amounts Array of borrowed Ticker assets amounts to repay
  /// @param collateralAsset Asset used for liquidation fee
  /// @dev Flashloan the debt tokens to liquidate, then use liquidation assets to repay the flashloan
  function liquidate (
    uint poolId, 
    address user,
    address[] memory options, 
    uint[] memory amounts,
    address collateralAsset
  )
    external
  {
    require(options.length == amounts.length, "ARRAY_LEN_MISMATCH");
    bytes memory params = abi.encode(1, poolId, user, collateralAsset); // mode = 1 -> liquidation
    (ILendingPool LP,,, address token0, address token1) = getPoolAddresses(poolId);
    
    uint[] memory flashtype = new uint[](options.length);
    for (uint8 i = 0; i< options.length; ){
      flashtype[i] = 0; // dont open debt for liquidations, need to repay
      unchecked { i+=1; }
    }
    LP.flashLoan( address(this), options, amounts, flashtype, msg.sender, params, 0);

    // send all tokens to liquidator
    cleanup(LP, msg.sender, token0);
    cleanup(LP, msg.sender, token1);
  }


  ////////////////////// REDUCING POSITION
  
  /// @notice Repays a TR debt and send tokens back to user
  /// @param poolId ID of the ROE lending pool
  /// @param user Owner of the debt
  /// @param debtAsset the borrowed LP token address
  /// @param repayAmount amount of borrowed tokens to repay; 0 or higher than current debt will repay all
  /// @param collateralAsset Asset used for liquidation fee
  function close(
    uint poolId, 
    address user,
    address debtAsset, 
    uint repayAmount,
    address collateralAsset
  ) 
    external
  {
    (ILendingPool LP,,, address token0, address token1) = getPoolAddresses(poolId);
    uint debt = ERC20(LP.getReserveData(debtAsset).variableDebtTokenAddress).balanceOf(user);
    if ( repayAmount > 0 && repayAmount < debt ) debt = repayAmount;
    require(debt > 0, "OPM: No Debt");
    debt = closeDebt(poolId, user, debtAsset, debt, collateralAsset);

    cleanup(LP, user, token0);
    cleanup(LP, user, token1);
    emit ReducedPosition(user, debtAsset, debt);
  }


  /// @notice Repays a TR debt
  /// @param poolId ID of the ROE lending pool
  /// @param user Owner of the debt to close. If user is address(this), we dont repay but just recreate tokens, flashloan will take care of getting them back
  /// @param debtAsset the borrowed LP token address
  /// @param repayAmount amount of borrowed tokens to repay; 0 or higher than current debt will repay all
  /// @param collateralAsset Asset used for liquidation fee
  function closeDebt(
    uint poolId, 
    address user,
    address debtAsset, 
    uint repayAmount,
    address collateralAsset
  ) 
    internal returns (uint debt)
  {
    (ILendingPool LP,,IUniswapV2Router01 ammRouter, address token0, address token1) = getPoolAddresses(poolId);
    sanityCheckUnderlying(debtAsset, token0, token1);
    require(collateralAsset == token0 || collateralAsset == token1, "OPM: Invalid Collateral Asset");
    uint amtA;
    uint amtB;
    // Add dust to be sure debt reformed >= debt outstanding
    debt = repayAmount + addDust(debtAsset, token0, token1);
    
    // Claim fees first so that deposit will match exactly
    TokenisableRange(debtAsset).claimFee();
    { //localize vars
      (uint token0Amount, uint token1Amount) = TokenisableRange(debtAsset).getTokenAmounts(debt);
      checkExpectedBalances(debtAsset, debt, token0Amount, token1Amount);
      checkSetAllowance(token0, debtAsset, token0Amount);
      checkSetAllowance(token1, debtAsset, token1Amount);
      // If called by this contract himself this is a liquidation, skip that step
      if (user != address(this) ){
        amtA = IERC20(LP.getReserveData(token0).aTokenAddress ).balanceOf(user);
        amtB = IERC20(LP.getReserveData(token1).aTokenAddress ).balanceOf(user);
        PMWithdraw(LP, user, token0, amtA );
        PMWithdraw(LP, user, token1, amtB );
        // If another user softLiquidates a share of the liquidation goes to the treasury
        if (user != msg.sender ) {
          uint feeAmount = calculateAndSendFee(poolId, token0Amount, token1Amount, collateralAsset);
          if (collateralAsset == token0) amtA -= feeAmount;
          else amtB -= feeAmount;
        }
      }
      else {
        // Assets are already present from liquidation
        amtA = ERC20(token0).balanceOf(user);
        amtB = ERC20(token1).balanceOf(user);
      }

      // swap if one token is missing - consider that there is enough 
      address[] memory path = new address[](2);
      if ( amtA < token0Amount ){
        path[0] = token1;
        path[1] = token0;
        swapTokensForExactTokens(ammRouter, token0Amount - amtA, amtB, path); 
      }
      else if ( amtB < token1Amount ){
        path[0] = token0;
        path[1] = token1;
        swapTokensForExactTokens(ammRouter, token1Amount - amtB, amtA, path); 
      }
      debt = TokenisableRange(debtAsset).deposit(token0Amount, token1Amount);
    }
    checkSetAllowance(debtAsset, address(LP), debt);
    
    // If user closes, repay debt, else tokens will be taken back by the flashloan
    if (user != address(this) ) LP.repay( debtAsset, debt, 2, user);
    {
      uint amt0 = ERC20(token0).balanceOf(address(this));
      uint amt1 = ERC20(token1).balanceOf(address(this));
      // edge case where after swapping exactly the tokens and repaying debt, dust causes remaining asset balance to be slightly higher than before repaying
      if (amtA > amt0) 
        amt0 = amtA - amt0;
      else 
        amt0 = 0;
      if (amtB > amt1) 
        amt1 = amtB - amt1;
      else 
        amt1 = 0;
      emit ClosePosition(user, debtAsset, debt, amt0, amt1);
    }
    
    // Swap other token back to collateral: this allows to control exposure
    if (user == msg.sender) swapTokens(poolId, collateralAsset == token0 ? token1 : token0, 0);
  }
  
  
  /// @notice Check that amounts to deposit in TR are matching expected balance based on oracle, to avoid sandwich attacks
  /// @param debtAsset the borrowed LP token address
  /// @param debtAmount the amount of debt
  /// @param token0Amount Amount of token0 used to liquidate the debt
  /// @param token1Amount Amount of token1 used to liquidate the debt
  function checkExpectedBalances(address debtAsset, uint debtAmount, uint token0Amount, uint token1Amount) internal view
  {
    IAaveOracle oracle = TokenisableRange(debtAsset).ORACLE();
    (ERC20 token0, uint8 decimals0) = TokenisableRange(debtAsset).TOKEN0();
    (ERC20 token1, uint8 decimals1) = TokenisableRange(debtAsset).TOKEN1();
    uint debtValue = TokenisableRange(debtAsset).latestAnswer() * debtAmount / 1e18;
    uint tokensValue = token0Amount * oracle.getAssetPrice(address(token0)) / 10**decimals0 + token1Amount * oracle.getAssetPrice(address(token1)) / 10**decimals1;
    // check that value of underlying tokens > 98% theoretical value  of TR asset, or that this is dust 
    require( 
      (debtValue < 1e8 && tokensValue < 1e8 )
      || (tokensValue > debtValue * 98 / 100 && tokensValue < debtValue * 102 / 100), 
      "OPM: Slippage Error"
    );
  }

  
  /// @notice Calculates the liquidation fee and sends it to the treasury
  /// @param poolId ROE pool Id
  /// @param token0Amount Amount of token0 used to liquidate the debt
  /// @param token1Amount Amount of token1 used to liquidate the debt
  /// @param collateralAsset Asset used for liquidation fee
  function calculateAndSendFee(
    uint poolId, 
    uint token0Amount, 
    uint token1Amount, 
    address collateralAsset
  ) internal returns (uint feeAmount) {
    (, IPriceOracle oracle,, address token0, address token1) = getPoolAddresses(poolId);
    
    uint feeValueE8 = token0Amount * oracle.getAssetPrice(token0) / 10**ERC20(token0).decimals()
                    + token1Amount * oracle.getAssetPrice(token1) / 10**ERC20(token1).decimals() ;
    feeAmount = feeValueE8 * 10**ERC20(collateralAsset).decimals() / 100 / oracle.getAssetPrice(collateralAsset);
    
    require(feeAmount <= IERC20(collateralAsset).balanceOf(address(this)), "OPM: Insufficient Collateral");
    IERC20(collateralAsset).safeTransfer(ROEROUTER.treasury(), feeAmount);
  }

  
  ////////////////////// SELL OPTIONS
  
  
  /// @notice Sell options
  /// @param poolId ID of the ROE lending pool
  /// @param optionAddress The TokenisableRange representing the option
  /// @param amount0 The amount of underlying token0 to add
  /// @param amount1 The amount of underlying token1 to add
  /// @dev Amounts aren't checked and will revert if wrong. In 99.9% cases one of the amounts should be 0
  /// @dev Collateral needs to be in Lending Pool already
  function sellOptions(
    uint poolId,
    address optionAddress,
    uint amount0,
    uint amount1
  )
    external
  {
    (ILendingPool LP, IPriceOracle oracle,, address token0, address token1 ) = getPoolAddresses(poolId);
    require( LP.getReserveData(optionAddress).aTokenAddress != address(0x0), "OPM: Invalid Address" );
    
    PMWithdraw(LP, msg.sender, token0, amount0);
    PMWithdraw(LP, msg.sender, token1, amount1);
    checkSetAllowance(token0, optionAddress, amount0);
    checkSetAllowance(token1, optionAddress, amount1);
    uint deposited = TokenisableRange(optionAddress).deposit(amount0, amount1);
    
    emit SellOptions(msg.sender, optionAddress, deposited, amount0, amount1 );
    cleanup(LP, msg.sender, optionAddress);
    cleanup(LP, msg.sender, token0);
    cleanup(LP, msg.sender, token1);
  }
  
  
  /// @notice Stop selling = remove liquidity from a TR
  /// @param poolId Id of the pool
  /// @param optionAddress Address of the TR asset
  /// @param amount Amount of TR asset redeemed
  function withdrawOptions(
    uint poolId,
    address optionAddress,
    uint amount
  )
    external
  {
    (ILendingPool LP,,, address token0, address token1 ) = getPoolAddresses(poolId);
    require( LP.getReserveData(optionAddress).aTokenAddress != address(0x0), "OPM: Invalid Address" );
    PMWithdraw(LP, msg.sender, optionAddress, amount);

    // Get output amounts from oracle to avoid sandwich
    (uint amount0, uint amount1) = TokenisableRange(optionAddress).withdraw(amount, 0, 0);
    checkExpectedBalances(optionAddress, amount, amount0, amount1);
    cleanup(LP, msg.sender, optionAddress);
    cleanup(LP, msg.sender, token0);
    cleanup(LP, msg.sender, token1);
  }
  
  
  ////////////////////// SWAP
  
  /// @notice Swap user assets; useful to change user risk profile
  /// @param poolId Id of the pool
  /// @param sourceAsset Asset to be swapped
  /// @param amount of asset to swap - if 0, swap all
  /// @return received Amount of target token received
  function swapTokens(uint poolId, address sourceAsset, uint amount) public returns (uint received) {
    (ILendingPool LP, IPriceOracle oracle,IUniswapV2Router01 router, address token0, address token1) = getPoolAddresses(poolId);
    require(sourceAsset == token0 || sourceAsset == token1, "OPM: Invalid Swap Asset");
    if (amount == 0) {
      amount = ERC20(LP.getReserveData(sourceAsset).aTokenAddress).balanceOf(msg.sender);
      if (amount == 0) return 0;
    }
    PMWithdraw(LP, msg.sender, sourceAsset, amount);

    address[] memory path = new address[](2);
    path[0] = sourceAsset ;
    path[1] = sourceAsset == token0 ? token1 : token0;
    received = swapExactTokensForTokens(router, oracle, amount, path);
    
    cleanup(LP, msg.sender, token0);
    cleanup(LP, msg.sender, token1);
    emit Swap(msg.sender, path[0], amount, path[1], received);
  }
  
  
  
  
  ////////////////////// HELPERS

  
  /// @notice Swaps assets for exact assets
  /// @param ammRouter AMM router
  /// @param oracle Price oracle
  /// @param amount Amount of target token received
  /// @param path The path [source, target] of the swap
  /// @return received Amount of target tokens received
  function swapExactTokensForTokens(IUniswapV2Router01 ammRouter, IPriceOracle oracle, uint amount, address[] memory path) 
    internal returns (uint256 received)
  {
    if (amount > 0 && AmountsRouter(address(ammRouter)).getAmountsOut(amount, path)[1] > 0){
      checkSetAllowance(path[0], address(ammRouter), amount);
      uint[] memory amounts = ammRouter.swapExactTokensForTokens(
        amount, 
        getTargetAmountFromOracle(oracle, path[0], amount, path[1]) * 99 / 100, // allow 1% slippage 
        path, 
        address(this), 
        block.timestamp
      );
      received = amounts[1];
    }
  }
  
  /// @notice Swaps assets for exact assets
  /// @param ammRouter AMM router
  /// @param recvAmount Amount of target token received
  /// @param maxAmount Amount of source token allowed to be spent minus margin
  /// @param path The path [source, target] of the swap
  function swapTokensForExactTokens(IUniswapV2Router01 ammRouter, uint recvAmount, uint maxAmount, address[] memory path) internal {
    checkSetAllowance(path[0], address(ammRouter), maxAmount);
    uint [] memory amountsIn = AmountsRouter(address(ammRouter)).getAmountsIn(recvAmount, path);
        
    require( amountsIn[0] <= maxAmount && amountsIn[0] > 0, "OPM: Invalid Swap Amounts" );
    require( amountsIn[0] <= ERC20(path[0]).balanceOf(address(this)), "OPM: Insufficient Token Amount" );
    amountsIn = ammRouter.swapTokensForExactTokens(
      recvAmount,
      maxAmount,
      path,
      address(this),
      block.timestamp
    );
  }
  

  /// @notice Calculate a target swap amount based on oracle-provided token prices
  /// @param oracle Price oracle
  /// @param assetA address of token A
  /// @param amountA Amount of toke A
  /// @param assetB address of token B
  /// @return amountB Amount of target token
  function getTargetAmountFromOracle(IPriceOracle oracle, address assetA, uint amountA, address assetB) 
    internal view returns (uint amountB) 
  {
    /**
      uint valueA = amountA * oracle.getAssetPrice(assetA) / 10**ERC20(assetA).decimals();
      uint valueB = amountB * oracle.getAssetPrice(assetB) / 10**ERC20(assetB).decimals();
      We expect valueA == valueB
    */
    uint priceAssetA = oracle.getAssetPrice(assetA);
    uint priceAssetB = oracle.getAssetPrice(assetB);
    require ( priceAssetA > 0 && priceAssetB > 0, "OPM: Invalid Oracle Price");
    amountB = amountA * priceAssetA * 10**ERC20(assetB).decimals() / 10**ERC20(assetA).decimals() / priceAssetB;
    require( amountB > 0, "OPM: Target Amount Too Low");
  }
  
  
  /// @notice Check that tr is a Tokenisable Range matching given tokens or revert
  /// @param tr Tokenisable range
  /// @param token0 Underlying token 0
  /// @param token1 Underlying token 1
  function sanityCheckUnderlying(address tr, address token0, address token1) internal {
    (ERC20 t0, ) = TokenisableRange(tr).TOKEN0();
    (ERC20 t1, ) = TokenisableRange(tr).TOKEN1();
    require(token0 == address(t0) && token1 == address(t1), "OPM: Invalid Debt Asset");
  }
  
  
  /// @notice Calculate a dust amount such that any underlying token amount would be larger than 100 units
  /// @param debtAsset The debt TR asset
  /// @param token0 Underlying token
  /// @param token1 Underlying token
  function addDust(address debtAsset, address token0, address token1) internal returns (uint amount){
    IAaveOracle oracle = TokenisableRange(debtAsset).ORACLE();
    uint scale0 = 10**(20 - ERC20(token0).decimals()) * oracle.getAssetPrice(token0) / 1e8;
    uint scale1 = 10**(20 - ERC20(token1).decimals()) * oracle.getAssetPrice(token1) / 1e8;
    
    if (scale0 > scale1) amount = scale0;
    else amount = scale1;
  }
}
