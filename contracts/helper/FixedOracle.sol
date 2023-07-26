pragma solidity ^0.8.0;

contract HardcodedPriceOracle {
    event SetHardcodedPrice(int256 price);

    int256 private hardcodedPrice;
    address private owner;
    

    modifier onlyOwner() {
        require(msg.sender == owner, "Only the owner can call this function.");
        _;
    }

    constructor(int256 _hardcodedPrice) {
        owner = msg.sender;
        hardcodedPrice = _hardcodedPrice;
    }

    function latestAnswer() external view returns (int256) {
        return hardcodedPrice;
    }

    function setHardcodedPrice(int256 _hardcodedPrice) external onlyOwner {
        hardcodedPrice = _hardcodedPrice;
        emit SetHardcodedPrice(_hardcodedPrice);
    }

    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        )
    {
        roundId = uint80(block.number);
        answer = hardcodedPrice;
        startedAt = block.timestamp;
        updatedAt = block.timestamp;
        answeredInRound = roundId;
    }
}
