// SPDX-License-Identifier: none
pragma solidity 0.8.19;

import "../../interfaces/AggregatorV3Interface.sol";

/*
    Contract takes 2 Chainlink feeds, and synthesises a composite price,
    by calculating priceA * priceB, and scaling to 8 decimals places, as
    the primary use is to scale / ETH to / USD
    E.g. Given TRIBE / ETH and ETH / USD, return TRIBE / USD
    
    Note that only latestAnswer() is calculated, and this is primarily meant 
    to be used with the Aave Market Oracles
*/
contract OracleConvert {
    AggregatorV3Interface public immutable CL_TOKENA;
    AggregatorV3Interface public immutable CL_TOKENB;
 
 
	/// @param clToken0 Underlying token0 ChainLink feed
	/// @param clToken1 Underlying token1 ChainLink feed
	constructor (address clToken0, address clToken1 ){
    require(clToken0 != address(0x0) && clToken1 != address(0x0), "Invalid address");
		CL_TOKENA = AggregatorV3Interface(clToken0);
		CL_TOKENB = AggregatorV3Interface(clToken1);
    require(CL_TOKENA.decimals() + CL_TOKENB.decimals() >= 16, "Decimals error");
	}

  /// @notice Get oracle decimals
  function decimals() external pure returns (uint8) {
    return 8;
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
  function latestAnswer() public view returns (int256) {
    uint priceA = uint(getAnswer(CL_TOKENA));
    uint priceB = uint(getAnswer(CL_TOKENB));
    return int(priceA * priceB / (10 ** (CL_TOKENB.decimals() + CL_TOKENA.decimals() - 8))); 
  }
  
  /**
   * @notice get data about the latest round. Consumers are encouraged to check
   * that they're receiving fresh data by inspecting the updatedAt and
   * answeredInRound return values.
   * Note that different underlying implementations of AggregatorV3Interface
   * have slightly different semantics for some of the return values. Consumers
   * should determine what implementations they expect to receive
   * data from and validate that they can properly handle return data from all
   * of them.
   * @return roundId is the round ID from the aggregator for which the data was
   * retrieved combined with an phase to ensure that round IDs get larger as
   * time moves forward.
   * @return answer is the answer for the given round
   * @return startedAt is the timestamp when the round was started.
   * (Only some AggregatorV3Interface implementations return meaningful values)
   * @return updatedAt is the timestamp when the round last was updated (i.e.
   * answer was last computed)
   * @return answeredInRound is the round ID of the round in which the answer
   * was computed.
   * (Only some AggregatorV3Interface implementations return meaningful values)
   * @dev Note that answer and updatedAt may change between queries.
   */
  function latestRoundData() external view returns (uint80 roundId, int256 answer, uint256 startedAt, uint256 updatedAt, uint80 answeredInRound) {
    return (type(uint80).max, latestAnswer(), block.timestamp, block.timestamp, type(uint80).max);
  }
}
