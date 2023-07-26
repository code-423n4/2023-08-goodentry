// SPDX-License-Identifier: none
pragma solidity 0.8.19;

import "../../interfaces/AggregatorV3Interface.sol";

interface UniswapV2Pair {
  function totalSupply() external view returns (uint);
  function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast);
  function token0() external view returns (address);
  function token1() external view returns (address);
}

interface IERC20 {
  function decimals() external view returns (uint8);
}

contract LPOracle {
  /* Matic Network Settings */
  AggregatorV3Interface public immutable CL_TOKENA;
  AggregatorV3Interface public immutable CL_TOKENB;
  UniswapV2Pair public immutable LP_TOKEN;
	uint8 public immutable decimalsA;
	uint8 public immutable decimalsB;

	/// @param lpToken UNI-LP token
	/// @param clToken0 Underlying token0 ChainLink feed
	/// @param clToken1 Underlying token1 ChainLink feed
	constructor (address lpToken, address clToken0, address clToken1 ){
    require(lpToken != address(0x0) && clToken0 != address(0x0) && clToken1 != address(0x0), "Invalid address");
		LP_TOKEN = UniswapV2Pair(lpToken);
		CL_TOKENA = AggregatorV3Interface(clToken0);
		CL_TOKENB = AggregatorV3Interface(clToken1);
		decimalsA = IERC20(UniswapV2Pair(lpToken).token0()).decimals();
		decimalsB = IERC20(UniswapV2Pair(lpToken).token1()).decimals();
	}

  /// @notice Get oracle decimals
  function decimals() external pure returns (uint8) {
    return 8;
  }

  /// @notice Calculate a square root 
  /// @param y Square root variable
  function sqrt(uint x) internal pure returns (uint y) {
    uint z = (x + 1) / 2;
    y = x;
    while (z < y) {
      y = z;
      z = (x / z + z) / 2;
    }
  }

  /// @notice Get the price for the latest available round of a feed
  /// @param priceFeed Price feed
  /// @return Latest price
  function getAnswer(AggregatorV3Interface priceFeed) internal view returns (int256) {
    (
      , 
      int price,
      ,
      uint timeStamp,
    ) = priceFeed.latestRoundData();
    require(timeStamp > 0, "Round not complete");
    return price;
  }

  /// @notice Get the oracle price for the latest available round
  /// @return Latest price
  function latestAnswer() external view returns (int256) {
    (uint a, uint b,) = LP_TOKEN.getReserves();

    uint priceA = uint(getAnswer(CL_TOKENA));
    uint priceB = uint(getAnswer(CL_TOKENB));
    /*
      a and b represents the amounts of asset0 and asset1 in the LP
      In the uniswap AMM model, a*b is always a constant k (ignoring fees)
      norm_a, norm_b represents a, b adjusted along the k curve such that it represents the amounts the uniswap pool will contain at the Chainlink oracle price 
  
      a*b = k = norm_a*norm_b
      norm_a * cl_price_a / decimals_a = norm_b * cl_price_b / decimals_b
      norm_b^2 = a*b * cl_price_a / decimals_a * decimals_b / cl_price_b
    */
    
    // Below line may potentially overflow, e.g. for TRIBE-FEI pair, where numA * numB *priceA * 10**18 > 2**256-1
    // uint norm_b = sqrt( a * b * priceA * 10**decimalsB / 10**decimalsA / priceB ); 
    
    // Code below attempts to relief some common overflow potential
    uint norm_b;
    if (decimalsB >= decimalsA) {
      norm_b = sqrt( a * b * priceA * 10**(decimalsB-decimalsA) / priceB );
    } else {
      norm_b = sqrt( a * b * priceA / 10**(decimalsA-decimalsB) / priceB );
    }
    uint norm_a = a * b / norm_b;

    /*
      The normalised positions (18 decimals) are multiplied with the chainlink value (8 decimals), giving val.
      val is divided by LP_TOKEN.totalSupply(), which has 18 decimals, and casted to an int
      The return value represents the value * 10**8 of a single LP token 
    */
    require(decimalsA <= 18 && decimalsB <= 18, "Incorrect tokens");
    uint val = norm_a * priceA * 10**(18-decimalsA) + norm_b * 10**(18-decimalsB) * priceB;
    return int(val / LP_TOKEN.totalSupply());
  }
}
