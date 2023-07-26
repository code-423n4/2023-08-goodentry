// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.19;

import "../interfaces/INonfungiblePositionManager.sol";
import "../interfaces/IUniswapV3Factory.sol";
import "../interfaces/IUniswapV3Pool.sol";
import "./openzeppelin-solidity/contracts/token/ERC20/ERC20.sol";
import "./openzeppelin-solidity/contracts/token/ERC20/utils/SafeERC20.sol";
import "./openzeppelin-solidity/contracts/utils/Strings.sol";
import "./openzeppelin-solidity/contracts/security/ReentrancyGuard.sol";
import "./lib/LiquidityAmounts.sol";
import "./lib/TickMath.sol";
import "../interfaces/IAaveOracle.sol";
import "../interfaces/IAaveOracle.sol";


/// @notice Tokenize a Uniswap V3 NFT position
contract TokenisableRange is ERC20("", ""), ReentrancyGuard {
  using SafeERC20 for ERC20;
  /// EVENTS
  event InitTR(address asset0, address asset1, uint128 startX10, uint128 endX10);
  event Deposit(address sender, uint trAmount);
  event Withdraw(address sender, uint trAmount);
  event ClaimFees(uint fee0, uint fee1);
  
  /// VARIABLES

  int24 public lowerTick;
  int24 public upperTick;
  uint24 public feeTier;
  
  uint256 public tokenId;
  uint256 public fee0;
  uint256 public fee1;
  
  struct ASSET {
    ERC20 token;
    uint8 decimals;
  }
  
  ASSET public TOKEN0;
  ASSET public TOKEN1;
  IAaveOracle public ORACLE;
  
  string _name;
  string _symbol;
  
  enum ProxyState { INIT_PROXY, INIT_LP, READY }
  ProxyState public status;
  address private creator;
  
  uint128 public liquidity;
  // @notice deprecated, keep to avoid beacon storage slot overwriting errors
  address public TREASURY_DEPRECATED = 0x22Cc3f665ba4C898226353B672c5123c58751692;
  uint public treasuryFee_deprecated = 20;
  
  // These are constant across chains - https://docs.uniswap.org/protocol/reference/deployments
  INonfungiblePositionManager constant public POS_MGR = INonfungiblePositionManager(0xC36442b4a4522E871399CD717aBDD847Ab11FE88); 
  IUniswapV3Factory constant public V3_FACTORY = IUniswapV3Factory(0x1F98431c8aD98523631AE4a59f267346ea31F984); 
  address constant public treasury = 0x22Cc3f665ba4C898226353B672c5123c58751692;
  uint constant public treasuryFee = 20;

  /// @notice Babylonian method for sqrt
  /// @param x sqrt parameter
  /// @return y Square root
  function sqrt(uint x) internal pure returns (uint y) {
      uint z = (x + 1) / 2;
      y = x;
      while (z < y) {
          y = z;
          z = (x / z + z) / 2;
      }
  }


  /// @notice Store range parameters
  /// @param _oracle Address of the IAaveOracle interface of the ROE lending pool
  /// @param asset0 Quote token address
  /// @param asset1 Base token address 
  /// @param startX10 Range lower price scaled by 1e10
  /// @param endX10 Range high price scaled by 1e10
  /// @param startName Name of the range lower bound 
  /// @param endName Name of the range higher bound
  /// @param isTicker Range is single tick liquidity around upperTick/startX10/startName
  function initProxy(IAaveOracle _oracle, ERC20 asset0, ERC20 asset1, uint128 startX10, uint128 endX10, string memory startName, string memory endName, bool isTicker) external {
    require(address(_oracle) != address(0x0), "Invalid oracle");
    require(status == ProxyState.INIT_PROXY, "!InitProxy");
    creator = msg.sender;
    status = ProxyState.INIT_LP;
    ORACLE = _oracle;
    
    TOKEN0.token    = asset0;
    TOKEN0.decimals = asset0.decimals();
    TOKEN1.token     = asset1;
    TOKEN1.decimals  = asset1.decimals();
    string memory quoteSymbol = asset0.symbol();
    string memory baseSymbol  = asset1.symbol();
        
    int24 _upperTick = TickMath.getTickAtSqrtRatio( uint160( 2**48 * sqrt( (2 ** 96 * (10 ** TOKEN1.decimals)) * 1e10 / (uint256(startX10) * 10 ** TOKEN0.decimals) ) ) );
    int24 _lowerTick = TickMath.getTickAtSqrtRatio( uint160( 2**48 * sqrt( (2 ** 96 * (10 ** TOKEN1.decimals)) * 1e10 / (uint256(endX10  ) * 10 ** TOKEN0.decimals) ) ) );
    
    if (isTicker) { 
      feeTier   = 5;
      int24 midleTick;
      midleTick = (_upperTick + _lowerTick) / 2;
      _upperTick = (midleTick + int24(feeTier)) - (midleTick + int24(feeTier)) % int24(feeTier * 2);
      _lowerTick = _upperTick - int24(feeTier) - int24(feeTier);
      _name     = string(abi.encodePacked("Ticker ", baseSymbol, " ", quoteSymbol, " ", startName, "-", endName));
     _symbol    = string(abi.encodePacked("T-",startName,"_",endName,"-",baseSymbol,"-",quoteSymbol));
    } else {
      feeTier   = 5;
      _lowerTick = (_lowerTick + int24(feeTier)) - (_lowerTick + int24(feeTier)) % int24(feeTier * 2);
      _upperTick = (_upperTick + int24(feeTier)) - (_upperTick + int24(feeTier)) % int24(feeTier * 2);
      _name     = string(abi.encodePacked("Ranger ", baseSymbol, " ", quoteSymbol, " ", startName, "-", endName));
      _symbol   = string(abi.encodePacked("R-",startName,"_",endName,"-",baseSymbol,"-",quoteSymbol));
    }
    lowerTick = _lowerTick;
    upperTick = _upperTick;
    emit InitTR(address(asset0), address(asset1), startX10, endX10);
  }
  

  /// @notice Get the name of this contract token
  /// @dev Override name, symbol and decimals from ERC20 inheritance
  function name()     public view virtual override returns (string memory) { return _name; }
  /// @notice Get the symbol of this contract token
  function symbol()   public view virtual override returns (string memory) { return _symbol; }


  /// @notice Initialize a TokenizableRange by adding assets in the underlying Uniswap V3 position
  /// @param n0 Amount of quote token added
  /// @param n1 Amount of base token added
  /// @notice The token amounts must be 95% correct or this will fail the Uniswap slippage check
  function init(uint n0, uint n1) external {
    require(status == ProxyState.INIT_LP, "!InitLP");
    require(msg.sender == creator, "Unallowed call");
    status = ProxyState.READY;
    TOKEN0.token.safeTransferFrom(msg.sender, address(this), n0);
    TOKEN1.token.safeTransferFrom(msg.sender, address(this), n1);
    TOKEN0.token.safeIncreaseAllowance(address(POS_MGR), n0);
    TOKEN1.token.safeIncreaseAllowance(address(POS_MGR), n1);
    (tokenId, liquidity, , ) = POS_MGR.mint( 
      INonfungiblePositionManager.MintParams({
         token0: address(TOKEN0.token),
         token1: address(TOKEN1.token),
         fee: feeTier * 100,
         tickLower: lowerTick,
         tickUpper: upperTick,
         amount0Desired: n0,
         amount1Desired: n1,
         amount0Min: n0 * 95 / 100,
         amount1Min: n1 * 95 / 100,
         recipient: address(this),
         deadline: block.timestamp
      })
    );
    
    // Transfer remaining assets back to user
    TOKEN0.token.safeTransfer( msg.sender,  TOKEN0.token.balanceOf(address(this)));
    TOKEN1.token.safeTransfer(msg.sender, TOKEN1.token.balanceOf(address(this)));
    _mint(msg.sender, 1e18);
    emit Deposit(msg.sender, 1e18);
  }
  
  
  /// @notice Claim the accumulated Uniswap V3 trading fees
  function claimFee() public {
    (uint256 newFee0, uint256 newFee1) = POS_MGR.collect( 
      INonfungiblePositionManager.CollectParams({
        tokenId: tokenId,
        recipient: address(this),
        amount0Max: type(uint128).max,
        amount1Max: type(uint128).max
      })
    );
    // If there's no new fees generated, skip compounding logic;
    if ((newFee0 == 0) && (newFee1 == 0)) return;  
    uint tf0 = newFee0 * treasuryFee / 100;
    uint tf1 = newFee1 * treasuryFee / 100;
    if (tf0 > 0) TOKEN0.token.safeTransfer(treasury, tf0);
    if (tf1 > 0) TOKEN1.token.safeTransfer(treasury, tf1);
    
    fee0 = fee0 + newFee0 - tf0;
    fee1 = fee1 + newFee1 - tf1;
    
    // Calculate expected balance,  
    (uint256 bal0, uint256 bal1) = returnExpectedBalanceWithoutFees(0, 0);
    
    // If accumulated more than 1% worth of fees, compound by adding fees to Uniswap position
    if ((fee0 * 100 > bal0 ) && (fee1 * 100 > bal1)) { 
      TOKEN0.token.safeIncreaseAllowance(address(POS_MGR), fee0);
      TOKEN1.token.safeIncreaseAllowance(address(POS_MGR), fee1);
      (uint128 newLiquidity, uint256 added0, uint256 added1) = POS_MGR.increaseLiquidity(
        INonfungiblePositionManager.IncreaseLiquidityParams({
          tokenId: tokenId,
          amount0Desired: fee0,
          amount1Desired: fee1,
          amount0Min: 0,
          amount1Min: 0,
          deadline: block.timestamp
        })
      );
      // check slippage: validate against value since token amounts can move widely
      uint token0Price = ORACLE.getAssetPrice(address(TOKEN0.token));
      uint token1Price = ORACLE.getAssetPrice(address(TOKEN1.token));
      uint addedValue = added0 * token0Price / 10**TOKEN0.decimals + added1 * token1Price / 10**TOKEN1.decimals;
      uint totalValue =   bal0 * token0Price / 10**TOKEN0.decimals +   bal1 * token1Price / 10**TOKEN1.decimals;
      uint liquidityValue = totalValue * newLiquidity / liquidity;
      require(addedValue > liquidityValue * 95 / 100 && liquidityValue > addedValue * 95 / 100, "TR: Claim Fee Slippage");
      fee0 -= added0;
      fee1 -= added1;
      liquidity = liquidity + newLiquidity;
    }
    emit ClaimFees(newFee0, newFee1);
  }
  
  
  /// @notice Deposit assets into the range
  /// @param n0 Amount of quote asset
  /// @param n1 Amount of base asset
  /// @return lpAmt Amount of LP tokens created
  function deposit(uint256 n0, uint256 n1) external nonReentrant returns (uint256 lpAmt) {
    // Once all assets were withdrawn after initialisation, this is considered closed
    // Prevents TR oracle values from being too manipulatable by emptying the range and redepositing 
    require(totalSupply() > 0, "TR Closed"); 
    
    claimFee();
    TOKEN0.token.transferFrom(msg.sender, address(this), n0);
    TOKEN1.token.transferFrom(msg.sender, address(this), n1);
    
    uint newFee0; 
    uint newFee1;
    // Calculate proportion of deposit that goes to pending fee pool, useful to deposit exact amount of liquidity and fully repay a position
    // Cannot repay only one side, if fees are both 0, or if one side is missing, skip adding fees here
      // if ( fee0+fee1 == 0 || (n0 == 0 && fee0 > 0) || (n1 == 0 && fee1 > 0) ) skip  
      // DeMorgan: !( (n0 == 0 && fee0 > 0) || (n1 == 0 && fee1 > 0) ) = !(n0 == 0 && fee0 > 0) && !(n0 == 0 && fee1 > 0)
    if ( fee0+fee1 > 0 && ( n0 > 0 || fee0 == 0) && ( n1 > 0 || fee1 == 0 ) ){
      address pool = V3_FACTORY.getPool(address(TOKEN0.token), address(TOKEN1.token), feeTier * 100);
      (uint160 sqrtPriceX96,,,,,,)  = IUniswapV3Pool(pool).slot0();
      (uint256 token0Amount, uint256 token1Amount) = LiquidityAmounts.getAmountsForLiquidity( sqrtPriceX96, TickMath.getSqrtRatioAtTick(lowerTick), TickMath.getSqrtRatioAtTick(upperTick), liquidity);
      if (token0Amount + fee0 > 0) newFee0 = n0 * fee0 / (token0Amount + fee0);
      if (token1Amount + fee1 > 0) newFee1 = n1 * fee1 / (token1Amount + fee1);
      fee0 += newFee0;
      fee1 += newFee1; 
      n0   -= newFee0;
      n1   -= newFee1;
    }

    TOKEN0.token.safeIncreaseAllowance(address(POS_MGR), n0);
    TOKEN1.token.safeIncreaseAllowance(address(POS_MGR), n1);

    // New liquidity is indeed the amount of liquidity added, not the total, despite being unclear in Uniswap doc
    (uint128 newLiquidity, uint256 added0, uint256 added1) = POS_MGR.increaseLiquidity(
      INonfungiblePositionManager.IncreaseLiquidityParams({
        tokenId: tokenId,
        amount0Desired: n0,
        amount1Desired: n1,
        amount0Min: n0 * 95 / 100,
        amount1Min: n1 * 95 / 100,
        deadline: block.timestamp
      })
    );
    
    uint256 feeLiquidity;

    // Stack too deep, so localising some variables for feeLiquidity calculations 
    // If we already clawed back fees earlier, do nothing, else we need to adjust returned liquidity
    if ( newFee0 == 0 && newFee1 == 0 ){
      uint256 TOKEN0_PRICE = ORACLE.getAssetPrice(address(TOKEN0.token));
      uint256 TOKEN1_PRICE = ORACLE.getAssetPrice(address(TOKEN1.token));
      require (TOKEN0_PRICE > 0 && TOKEN1_PRICE > 0, "Invalid Oracle Price");
      // Calculate the equivalent liquidity amount of the non-yet compounded fees
      // Assume linearity for liquidity in same tick range; calculate feeLiquidity equivalent and consider it part of base liquidity 
      feeLiquidity = newLiquidity * ( (fee0 * TOKEN0_PRICE / 10 ** TOKEN0.decimals) + (fee1 * TOKEN1_PRICE / 10 ** TOKEN1.decimals) )   
                                    / ( (added0   * TOKEN0_PRICE / 10 ** TOKEN0.decimals) + (added1   * TOKEN1_PRICE / 10 ** TOKEN1.decimals) ); 
    }
                                     
    lpAmt = totalSupply() * newLiquidity / (liquidity + feeLiquidity); 
    liquidity = liquidity + newLiquidity;
    
    _mint(msg.sender, lpAmt);
    TOKEN0.token.safeTransfer( msg.sender, n0 - added0);
    TOKEN1.token.safeTransfer( msg.sender, n1 - added1);
    emit Deposit(msg.sender, lpAmt);
  }
  
  
  /// @notice Withdraw assets from a range
  /// @param lp Amount of tokens withdrawn
  /// @param amount0Min Minimum amount of quote token withdrawn
  /// @param amount1Min Minimum amount of base token withdrawn
  function withdraw(uint256 lp, uint256 amount0Min, uint256 amount1Min) external nonReentrant returns (uint256 removed0, uint256 removed1) {
    claimFee();
    uint removedLiquidity = uint(liquidity) * lp / totalSupply();
    (removed0, removed1) = POS_MGR.decreaseLiquidity(
      INonfungiblePositionManager.DecreaseLiquidityParams({
        tokenId: tokenId,
        liquidity: uint128(removedLiquidity),
        amount0Min: amount0Min,
        amount1Min: amount1Min,
        deadline: block.timestamp
      })
    );
    liquidity = uint128(uint256(liquidity) - removedLiquidity); 
    
    POS_MGR.collect( 
      INonfungiblePositionManager.CollectParams({
        tokenId: tokenId,
        recipient: msg.sender,
        amount0Max: uint128(removed0),
        amount1Max: uint128(removed1)
      })
    );
    // Handle uncompounded fees
    if (fee0 > 0) {
      TOKEN0.token.safeTransfer( msg.sender, fee0 * lp / totalSupply());
      removed0 += fee0 * lp / totalSupply();
      fee0 -= fee0 * lp / totalSupply();
    } 
    if (fee1 > 0) {
      TOKEN1.token.safeTransfer(  msg.sender, fee1 * lp / totalSupply());
      removed1 += fee1 * lp / totalSupply();
      fee1 -= fee1 * lp / totalSupply();
    }
    _burn(msg.sender, lp);
    emit Withdraw(msg.sender, lp);
  }
  

  /// @notice Calculate the balance of underlying assets based on the assets price
  /// @param TOKEN0_PRICE Base token price
  /// @param TOKEN1_PRICE Quote token price
  function returnExpectedBalanceWithoutFees(uint TOKEN0_PRICE, uint TOKEN1_PRICE) internal view returns (uint256 amt0, uint256 amt1) {
    // if 0 get price from oracle
    if (TOKEN0_PRICE == 0) TOKEN0_PRICE = ORACLE.getAssetPrice(address(TOKEN0.token));
    if (TOKEN1_PRICE == 0) TOKEN1_PRICE = ORACLE.getAssetPrice(address(TOKEN1.token));

    (amt0, amt1) = LiquidityAmounts.getAmountsForLiquidity( uint160( sqrt( (2 ** 192 * ((TOKEN0_PRICE * 10 ** TOKEN1.decimals) / TOKEN1_PRICE)) / ( 10 ** TOKEN0.decimals ) ) ), TickMath.getSqrtRatioAtTick(lowerTick), TickMath.getSqrtRatioAtTick(upperTick),  liquidity);
  }
    
    
  /// @notice Calculate the balance of underlying assets based on the assets price, excluding fees
  function returnExpectedBalance(uint TOKEN0_PRICE, uint TOKEN1_PRICE) public view returns (uint256 amt0, uint256 amt1) {
    (amt0, amt1) = returnExpectedBalanceWithoutFees(TOKEN0_PRICE, TOKEN1_PRICE);
    amt0 += fee0;
    amt1 += fee1;
  }

  /// @notice Return the price of LP tokens based on the underlying assets price
  /// @param TOKEN0_PRICE Base token price
  /// @param TOKEN1_PRICE Quote token price
  function getValuePerLPAtPrice(uint TOKEN0_PRICE, uint TOKEN1_PRICE) public view returns (uint256 priceX1e8) {
    if ( totalSupply() == 0 ) return 0;
    (uint256 amt0, uint256 amt1) = returnExpectedBalance(TOKEN0_PRICE, TOKEN1_PRICE);
    uint totalValue = TOKEN0_PRICE * amt0 / (10 ** TOKEN0.decimals) + amt1 * TOKEN1_PRICE / (10 ** TOKEN1.decimals);
    return totalValue * 1e18 / totalSupply();
  } 

  
  /// @notice Return the price of the LP token
  function latestAnswer() public view returns (uint256 priceX1e8) {
    return getValuePerLPAtPrice(ORACLE.getAssetPrice(address(TOKEN0.token)), ORACLE.getAssetPrice(address(TOKEN1.token)));
  }
  
  
  /// @notice Return the underlying tokens amounts for a given TR balance excluding the fees
  /// @param amount Amount of tokens we want the underlying amounts for
  function getTokenAmountsExcludingFees(uint amount) public view returns (uint token0Amount, uint token1Amount){
    address pool = V3_FACTORY.getPool(address(TOKEN0.token), address(TOKEN1.token), feeTier * 100);
    (uint160 sqrtPriceX96,,,,,,)  = IUniswapV3Pool(pool).slot0();
    (token0Amount, token1Amount) = LiquidityAmounts.getAmountsForLiquidity( sqrtPriceX96, TickMath.getSqrtRatioAtTick(lowerTick), TickMath.getSqrtRatioAtTick(upperTick),  uint128 ( uint(liquidity) * amount / totalSupply() ) );
  }  
  
  
  /// @notice Return the underlying tokens amounts for a given TR balance
  /// @param amount Amount of tokens we want the underlying amounts for
  function getTokenAmounts(uint amount) external view returns (uint token0Amount, uint token1Amount){
    (token0Amount, token1Amount) = getTokenAmountsExcludingFees(amount);
    token0Amount += fee0 * amount / totalSupply();
    token1Amount += fee1 * amount / totalSupply();
  }

}