// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.19;

import "./openzeppelin-solidity/contracts/access/Ownable.sol";
import "./openzeppelin-solidity/contracts/token/ERC20/ERC20.sol";
import "./openzeppelin-solidity/contracts/token/ERC20/utils/SafeERC20.sol";
import "./openzeppelin-solidity/contracts/security/ReentrancyGuard.sol";
import "../interfaces/IAaveLendingPoolV2.sol";
import "../interfaces/IUniswapV3Pool.sol";
import "../interfaces/IWETH.sol";
import "./RangeManager.sol";
import "./RoeRouter.sol";


/**
GeVault is a reblancing vault that holds TokenisableRanges tickers
Functionalities:
- Hold a list of tickers for a single pair, evenly spaced
- Hold balances of those tickers, deposited in the ROE LP
- Deposit one underlying asset split evenly into 2 or more consecutive ticks above/below the current price
- Withdraw one underlying asset, taken out evenly from 2 or more consecutive ticks
- Calculate the current balance of assets

Design:
 
 */
contract GeVault is ERC20, Ownable, ReentrancyGuard {
  using SafeERC20 for ERC20;
  
  event Deposit(address indexed sender, address indexed token, uint amount, uint liquidity);
  event Withdraw(address indexed sender, address indexed token, uint amount, uint liquidity);
  event PushTick(address indexed ticker);
  event ShiftTick(address indexed ticker);
  event ModifyTick(address indexed ticker, uint index);
  event Rebalance(uint tickIndex);
  event SetEnabled(bool isEnabled);
  event SetTreasury(address treasury);
  event SetFee(uint baseFeeX4);
  event SetTvlCap(uint tvlCap);

  RangeManager rangeManager; 
  /// @notice Ticks properly ordered in ascending price order
  TokenisableRange[] public ticks;
  
  /// @notice Tracks the beginning of active ticks: the next 4 ticks are the active
  uint public tickIndex; 
  /// @notice Pair tokens
  ERC20 public token0;
  ERC20 public token1;
  bool public isEnabled = true;
  /// @notice Pool base fee 
  uint public baseFeeX4 = 20;
  /// @notice Max vault TVL with 8 decimals
  uint public tvlCap = 1e12;
  
  /// CONSTANTS 
  /// immutable keyword removed for coverage testing bug in brownie
  address public treasury;
  IUniswapV3Pool public uniswapPool;
  ILendingPool public lendingPool;
  IPriceOracle public oracle;
  uint public constant nearbyRanges = 2;
  IWETH public WETH;
  bool public baseTokenIsToken0;
  

  constructor(
    address _treasury, 
    address roeRouter, 
    address _uniswapPool, 
    uint poolId, 
    string memory name, 
    string memory symbol,
    address weth,
    bool _baseTokenIsToken0
  ) 
    ERC20(name, symbol)
  {
    require(_treasury != address(0x0), "GEV: Invalid Treasury");
    require(_uniswapPool != address(0x0), "GEV: Invalid Pool");
    require(weth != address(0x0), "GEV: Invalid WETH");

    (address lpap, address _token0, address _token1,, ) = RoeRouter(roeRouter).pools(poolId);
    token0 = ERC20(_token0);
    token1 = ERC20(_token1);
    
    lendingPool = ILendingPool(ILendingPoolAddressesProvider(lpap).getLendingPool());
    oracle = IPriceOracle(ILendingPoolAddressesProvider(lpap).getPriceOracle());
    treasury = _treasury;
    uniswapPool = IUniswapV3Pool(_uniswapPool);
    WETH = IWETH(weth);
    baseTokenIsToken0 = _baseTokenIsToken0;
  }
  
  
  //////// ADMIN
  
  
  /// @notice Set pool status
  /// @param _isEnabled Pool status
  function setEnabled(bool _isEnabled) public onlyOwner { 
    isEnabled = _isEnabled; 
    emit SetEnabled(_isEnabled);
  }
  
  /// @notice Set treasury address
  /// @param newTreasury New address
  function setTreasury(address newTreasury) public onlyOwner { 
    treasury = newTreasury; 
    emit SetTreasury(newTreasury);
  }


  /// @notice Add a new ticker to the list
  /// @param tr Tick address
  function pushTick(address tr) public onlyOwner {
    TokenisableRange t = TokenisableRange(tr);
    (ERC20 t0,) = t.TOKEN0();
    (ERC20 t1,) = t.TOKEN1();
    require(t0 == token0 && t1 == token1, "GEV: Invalid TR");
    if (ticks.length == 0) ticks.push(t);
    else {
      // Check that tick is properly ordered
      if (baseTokenIsToken0) 
        require( t.lowerTick() > ticks[ticks.length-1].upperTick(), "GEV: Push Tick Overlap");
      else 
        require( t.upperTick() < ticks[ticks.length-1].lowerTick(), "GEV: Push Tick Overlap");
      
      ticks.push(TokenisableRange(tr));
    }
    emit PushTick(tr);
  }  


  /// @notice Add a new ticker to the list
  /// @param tr Tick address
  function shiftTick(address tr) public onlyOwner {
    TokenisableRange t = TokenisableRange(tr);
    (ERC20 t0,) = t.TOKEN0();
    (ERC20 t1,) = t.TOKEN1();
    require(t0 == token0 && t1 == token1, "GEV: Invalid TR");
    if (ticks.length == 0) ticks.push(t);
    else {
      // Check that tick is properly ordered
      if (!baseTokenIsToken0) 
        require( t.lowerTick() > ticks[0].upperTick(), "GEV: Shift Tick Overlap");
      else 
        require( t.upperTick() < ticks[0].lowerTick(), "GEV: Shift Tick Overlap");
      
      // extend array by pushing last elt
      ticks.push(ticks[ticks.length-1]);
      // shift each element
      if (ticks.length > 2){
        for (uint k = 0; k < ticks.length - 2; k++) 
          ticks[ticks.length - 2 - k] = ticks[ticks.length - 3 - k];
        }
      // add new tick in first place
      ticks[0] = t;
    }
    emit ShiftTick(tr);
  }


  /// @notice Modify ticker
  /// @param tr New tick address
  /// @param index Tick to modify
  function modifyTick(address tr, uint index) public onlyOwner {
    (ERC20 t0,) = TokenisableRange(tr).TOKEN0();
    (ERC20 t1,) = TokenisableRange(tr).TOKEN1();
    require(t0 == token0 && t1 == token1, "GEV: Invalid TR");
    ticks[index] = TokenisableRange(tr);
    emit ModifyTick(tr, index);
  }
  
  /// @notice Ticks length getter
  /// @return len Ticks length
  function getTickLength() public view returns(uint len){
    len = ticks.length;
  }
  
  /// @notice Set the base fee
  /// @param newBaseFeeX4 New base fee in E4
  function setBaseFee(uint newBaseFeeX4) public onlyOwner {
  require(newBaseFeeX4 < 1e4, "GEV: Invalid Base Fee");
    baseFeeX4 = newBaseFeeX4;
    emit SetFee(newBaseFeeX4);
  }
  
  /// @notice Set the TVL cap
  /// @param newTvlCap New TVL cap
  function setTvlCap(uint newTvlCap) public onlyOwner {
    tvlCap = newTvlCap;
    emit SetTvlCap(newTvlCap);
  }
  
  
  //////// PUBLIC FUNCTIONS
  
    
  /// @notice Rebalance tickers
  /// @dev Provide the list of tickers from 
  function rebalance() public {
    require(poolMatchesOracle(), "GEV: Oracle Error");
    removeFromAllTicks();
    if (isEnabled) deployAssets();
  }
  

  /// @notice Withdraw assets from the ticker
  /// @param liquidity Amount of GEV tokens to redeem; if 0, redeem all
  /// @param token Address of the token redeemed for
  /// @return amount Total token returned
  /// @dev For simplicity+efficieny, withdrawal is like a rebalancing, but a subset of the tokens are sent back to the user before redeploying
  function withdraw(uint liquidity, address token) public nonReentrant returns (uint amount) {
    require(poolMatchesOracle(), "GEV: Oracle Error");
    if (liquidity == 0) liquidity = balanceOf(msg.sender);
    require(liquidity <= balanceOf(msg.sender), "GEV: Insufficient Balance");
    require(liquidity > 0, "GEV: Withdraw Zero");
    
    uint vaultValueX8 = getTVL();
    uint valueX8 = vaultValueX8 * liquidity / totalSupply();
    amount = valueX8 * 10**ERC20(token).decimals() / oracle.getAssetPrice(token);
    uint fee = amount * getAdjustedBaseFee(token == address(token1)) / 1e4;
    
    _burn(msg.sender, liquidity);
    removeFromAllTicks();
    ERC20(token).safeTransfer(treasury, fee);
    uint bal = amount - fee;

    if (token == address(WETH)){
      WETH.withdraw(bal);
      payable(msg.sender).transfer(bal);
    }
    else {
      ERC20(token).safeTransfer(msg.sender, bal);
    }
    
    // if pool enabled, deploy assets in ticks, otherwise just let assets sit here until totally withdrawn
    if (isEnabled) deployAssets();
    emit Withdraw(msg.sender, token, amount, liquidity);
  }


  /// @notice deposit tokens in the pool, convert to WETH if necessary
  /// @param token Token address
  /// @param amount Amount of token deposited
  function deposit(address token, uint amount) public payable nonReentrant returns (uint liquidity) 
  {
    require(isEnabled, "GEV: Pool Disabled");
    require(poolMatchesOracle(), "GEV: Oracle Error");
    require(token == address(token0) || token == address(token1), "GEV: Invalid Token");
    require(amount > 0 || msg.value > 0, "GEV: Deposit Zero");
    
    // Wrap if necessary and deposit here
    if (msg.value > 0){
      require(token == address(WETH), "GEV: Invalid Weth");
      // wraps ETH by sending to the wrapper that sends back WETH
      WETH.deposit{value: msg.value}();
      amount = msg.value;
    }
    else { 
      ERC20(token).safeTransferFrom(msg.sender, address(this), amount);
    }
    
    // Send deposit fee to treasury
    uint fee = amount * getAdjustedBaseFee(token == address(token0)) / 1e4;
    ERC20(token).safeTransfer(treasury, fee);
    uint valueX8 = oracle.getAssetPrice(token) * (amount - fee) / 10**ERC20(token).decimals();
    require(tvlCap > valueX8 + getTVL(), "GEV: Max Cap Reached");

    uint vaultValueX8 = getTVL();
    uint tSupply = totalSupply();
    // initial liquidity at 1e18 token ~ $1
    if (tSupply == 0 || vaultValueX8 == 0)
      liquidity = valueX8 * 1e10;
    else {
      liquidity = tSupply * valueX8 / vaultValueX8;
    }
    
    rebalance();
    require(liquidity > 0, "GEV: No Liquidity Added");
    _mint(msg.sender, liquidity);    
    emit Deposit(msg.sender, token, amount, liquidity);
  }
  
  
  /// @notice Get value of 1e18 GEV tokens
  /// @return priceX8 price of 1e18 tokens with 8 decimals
  function latestAnswer() external view returns (uint256 priceX8) {
    uint supply = totalSupply();
    if (supply == 0) return 0;
    uint vaultValue = getTVL();
    priceX8 = vaultValue * 1e18 / supply;
  }
  
  
  /// @notice Get vault underlying assets
  function getReserves() public view returns (uint amount0, uint amount1){
    for (uint k = 0; k < ticks.length; k++){
      TokenisableRange t = ticks[k];
      address aTick = lendingPool.getReserveData(address(t)).aTokenAddress;
      uint bal = ERC20(aTick).balanceOf(address(this));
      (uint amt0, uint amt1) = t.getTokenAmounts(bal);
      amount0 += amt0;
      amount1 += amt1;
    }
  }


  //////// INTERNAL FUNCTIONS
  
  /// @notice Remove assets from all the underlying ticks
  function removeFromAllTicks() internal {
    for (uint k = 0; k < ticks.length; k++){
      removeFromTick(k);
    }    
  }
  
  
  /// @notice Remove from tick
  function removeFromTick(uint index) internal {
    TokenisableRange tr = ticks[index];
    address aTokenAddress = lendingPool.getReserveData(address(tr)).aTokenAddress;
    uint aBal = ERC20(aTokenAddress).balanceOf(address(this));
    uint sBal = tr.balanceOf(aTokenAddress);

    // if there are less tokens available than the balance (because of outstanding debt), withdraw what's available
    if (aBal > sBal) aBal = sBal;
    if (aBal > 0){
      lendingPool.withdraw(address(tr), aBal, address(this));
      tr.withdraw(aBal, 0, 0);
    }
  }
  
  
  /// @notice 
  function deployAssets() internal { 
    uint newTickIndex = getActiveTickIndex();
    uint availToken0 = token0.balanceOf(address(this));
    uint availToken1 = token1.balanceOf(address(this));
    
    // Check which is the main token
    (uint amount0ft, uint amount1ft) = ticks[newTickIndex].getTokenAmountsExcludingFees(1e18);
    uint tick0Index = newTickIndex;
    uint tick1Index = newTickIndex + 2;
    if (amount1ft > 0){
      tick0Index = newTickIndex + 2;
      tick1Index = newTickIndex;
    }
    
    // Deposit into the ticks + into the LP
    if (availToken0 > 0){
      depositAndStash(ticks[tick0Index], availToken0 / 2, 0);
      depositAndStash(ticks[tick0Index+1], availToken0 / 2, 0);
    }
    if (availToken1 > 0){
      depositAndStash(ticks[tick1Index], 0, availToken1 / 2);
      depositAndStash(ticks[tick1Index+1], 0, availToken1 / 2);
    }
    
    if (newTickIndex != tickIndex) tickIndex = newTickIndex;
    emit Rebalance(tickIndex);
  }
  
  
  /// @notice Checks that the pool price isn't manipulated
  function poolMatchesOracle() public view returns (bool matches){
    (uint160 sqrtPriceX96,,,,,,) = uniswapPool.slot0();
    
    uint decimals0 = token0.decimals();
    uint decimals1 = token1.decimals();
    uint priceX8 = 10**decimals0;
    // Overflow if dont scale down the sqrtPrice before div 2*192
    priceX8 = priceX8 * uint(sqrtPriceX96 / 2 ** 12) ** 2 * 1e8 / 2**168;
    priceX8 = priceX8 / 10**decimals1;
    uint oraclePrice = 1e8 * oracle.getAssetPrice(address(token0)) / oracle.getAssetPrice(address(token1));
    if (oraclePrice < priceX8 * 101 / 100 && oraclePrice > priceX8 * 99 / 100) matches = true;
  }


  /// @notice Helper that checks current allowance and approves if necessary
  /// @param token Target token
  /// @param spender Spender
  /// @param amount Amount below which we need to approve the token spending
  function checkSetApprove(address token, address spender, uint amount) private {
    if ( ERC20(token).allowance(address(this), spender) < amount ) ERC20(token).safeIncreaseAllowance(spender, type(uint256).max);
  }
  
  
  /// @notice Calculate the vault total ticks value
  /// @return valueX8 Total value of the vault with 8 decimals
  function getTVL() public view returns (uint valueX8){
    for(uint k=0; k<ticks.length; k++){
      TokenisableRange t = ticks[k];
      uint bal = getTickBalance(k);
      valueX8 += bal * t.latestAnswer() / 1e18;
    }
  }
  
  
  /// @notice Deposit assets in a ticker, and the ticker in lending pool
  /// @param t Tik address
  /// @return liquidity The amount of ticker liquidity added
  function depositAndStash(TokenisableRange t, uint amount0, uint amount1) internal returns (uint liquidity){
    checkSetApprove(address(token0), address(t), amount0);
    checkSetApprove(address(token1), address(t), amount1);
    liquidity = t.deposit(amount0, amount1);
    
    uint bal = t.balanceOf(address(this));
    if (bal > 0){
      checkSetApprove(address(t), address(lendingPool), bal);
      lendingPool.deposit(address(t), bal, address(this), 0);
    }
  }
  
  
  /// @notice Get balance of tick deposited in GE
  /// @param index Tick index
  /// @return liquidity Amount of Ticker
  function getTickBalance(uint index) public view returns (uint liquidity) {
    TokenisableRange t = ticks[index];
    address aTokenAddress = lendingPool.getReserveData(address(t)).aTokenAddress;
    liquidity = ERC20(aTokenAddress).balanceOf(address(this));
  }
  
  
  /// @notice Return first valid tick
  function getActiveTickIndex() public view returns (uint activeTickIndex) {
    if (ticks.length >= 5){
      // looking for index at which the underlying asset differs from the next tick
      for (activeTickIndex = 0; activeTickIndex < ticks.length - 3; activeTickIndex++){
        (uint amt0, uint amt1) = ticks[activeTickIndex+1].getTokenAmountsExcludingFees(1e18);
        (uint amt0n, uint amt1n) = ticks[activeTickIndex+2].getTokenAmountsExcludingFees(1e18);
        if ( (amt0 == 0 && amt0n > 0) || (amt1 == 0 && amt1n > 0) )
          break;
      }
    }
  }


  /// @notice Get deposit fee
  /// @param increaseToken0 Whether (token0 added || token1 removed) or not
  /// @dev Simple linear model: from baseFeeX4 / 2 to baseFeeX4 * 2
  /// @dev Call before withdrawing from ticks or reserves will both be 0
  function getAdjustedBaseFee(bool increaseToken0) public view returns (uint adjustedBaseFeeX4) {
    (uint res0, uint res1) = getReserves();
    uint value0 = res0 * oracle.getAssetPrice(address(token0)) / 10**token0.decimals();
    uint value1 = res1 * oracle.getAssetPrice(address(token1)) / 10**token1.decimals();

    if (increaseToken0)
      adjustedBaseFeeX4 = baseFeeX4 * value0 / (value1 + 1);
    else
      adjustedBaseFeeX4 = baseFeeX4 * value1 / (value0 + 1);

    // Adjust from -50% to +50%
    if (adjustedBaseFeeX4 < baseFeeX4 / 2) adjustedBaseFeeX4 = baseFeeX4 / 2;
    if (adjustedBaseFeeX4 > baseFeeX4 * 3 / 2) adjustedBaseFeeX4 = baseFeeX4 * 3 / 2;
  }


  /// @notice fallback: deposit unless it's WETH being unwrapped
  receive() external payable {
    if(msg.sender != address(WETH)) deposit(address(WETH), msg.value);
  }
  
}  