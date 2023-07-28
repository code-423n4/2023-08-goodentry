# Good Entry 👍

![GoodEntry](/goodentry.jpg)

👍 GoodEntry is a decentralized derivatives marketbuilt on top of Uniswap v3, and designed to offer protection for users engaged in trading or yield-generation activities.

## Good Entry audit details
- Total Prize Pool: $91,500 USDC 
  - HM awards: $46,250 USDC 
  - Analysis awards: $2,500 USDC 
  - QA awards: $1,250 USDC 
  - Bot Race awards: $3,750 USDC 
  - Gas awards: $1,250 USDC 
  - Judge awards: $6,000 USDC 
  - Lookout awards: $4,000 USDC 
  - Scout awards: $500 USDC 
  - Mitigation Review: $26,000 USDC (*Opportunity goes to top 3 certified wardens based on placement in this audit.*)
- Join [C4 Discord](https://discord.gg/code4rena) to register
- Submit findings [using the C4 form](https://code4rena.com/contests/2023-08-good-entry/submit)
- [Read our guidelines for more details](https://docs.code4rena.com/roles/wardens)
- Starts August 1, 2023 20:00 UTC 
- Ends August 8, 2023 20:00 UTC 

# Automated Findings / Publicly Known Issues
Automated findings output for the audit can be found [here](add link to report) within 24 hours of audit opening.
*Note for C4 wardens: Anything included in the automated findings output is considered a publicly known issue and is ineligible for awards.*

- We know that the liveliness of the oracle can be an issue, but we dont check in our contracts as anyway the Aave lending pool wouldn't work in case of stale/zero price feed.
- We also know that there can be some side effects when the supply of tokens is drained from the lending pool (borrowing), leading to positions that can't be closed, we know how to handle that though.

## Overview

GoodEntry is a perpetual options trading platform, or protected perps: user can trade perps with limited downside. It is built on top of Uniswap v3 and relies on single tick liquidity. It consists of:

- Tokenized Uniswap v3 positions (TR), with a manager, oracle, and price manipulation resistance
- ezVaults, holding TRs, and rebalancing the underlying liquidity as needed
- A lending pool, forked from Aave v2 (out of audit scope)
- A router that whitelists allowed addresses (such as allowed swap pools)

The core idea is that single tick liquidity in Uniswap behaves as a limit order, whose payout is similar to writing an option.
Borrowing such liquidity and removing it from the tick gives a pyout similar to buying an option.

For more details, check the [Gitbook doc](https://gitbook.goodentry.io/).

### Additional Context
- [Website](https://goodentry.io)
- [Twitter](https://twitter.com/goodentrylabs
- [Discord](https://discord.com/invite/goodentry)
- [Documentation](https://gitbook.goodentry.io/)
- [Deployed contracts](https://gitbook.goodentry.io/contracts)
- [Previous audits](https://gitbook.goodentry.io/audits)

## Scope

| File                                                                                                                                                  | Description                                                                                                                       | SLOC |
| ----------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ---- |
| [OptionsPositionManager.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/PositionManager/OptionsPositionManager.sol)          | Leverage/deleverage tool for Tokenized Ranges + risk management/liquidation tool, non asset bearing                               | 350  |
| [GeVault.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/GeVault.sol)                                                        | Holds single tick Tokenisable Ranges                                                                                              | 296  |
| [TokenisableRange.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/TokenisableRange.sol)                                      | Holds UniV3 NFTs and tokenises the ranges                                                                                         | 265  |
| [IAaveLendingPoolV2.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IAaveLendingPoolV2.sol)                       |                                                                                                                                   | 176  |
| [V3Proxy.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/helper/V3Proxy.sol)                                                 |                                                                                                                                   | 170  |
| [RangeManager.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/RangeManager.sol)                                              | Assists with creation and tracking of V3 TokenisableRanges, and helping user enter and exit these ranges through the Lending Pool | 144  |
| [IUniswapV2Router01.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IUniswapV2Router01.sol)                       |                                                                                                                                   | 141  |
| [INonfungiblePositionManager.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/INonfungiblePositionManager.sol)     |                                                                                                                                   | 95   |
| [ILendingPoolConfigurator.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/ILendingPoolConfigurator.sol)           |                                                                                                                                   | 89   |
| [PositionManager.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/PositionManager/PositionManager.sol)                        | Basic reusable functions                                                                                                          | 80   |
| [LPOracle.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/helper/LPOracle.sol)                                               |                                                                                                                                   | 62   |
| [IAaveIncentivesController.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IAaveIncentivesController.sol)         |                                                                                                                                   | 58   |
| [RoeRouter.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/RoeRouter.sol)                                                    | Whitelists GE pools                                                                                                               | 53   |
| [ISwapRouter.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/ISwapRouter.sol)                                     |                                                                                                                                   | 43   |
| [IUniswapV2Pair.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IUniswapV2Pair.sol)                               |                                                                                                                                   | 43   |
| [FixedOracle.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/helper/FixedOracle.sol)                                         |                                                                                                                                   | 38   |
| [IAToken.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IAToken.sol)                                             |                                                                                                                                   | 35   |
| [PoolAddress.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/PoolAddress.sol)                                     |                                                                                                                                   | 34   |
| [OracleConvert.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/helper/OracleConvert.sol/)                                    |                                                                                                                                   | 33   |
| [ILendingPoolAddressesProvider.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/ILendingPoolAddressesProvider.sol) |                                                                                                                                   | 32   |
| [AggregatorV3Interface.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/AggregatorV3Interface.sol)                 |                                                                                                                                   | 26   |
| [IUniswapV3Factory.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IUniswapV3Factory.sol)                         |                                                                                                                                   | 26   |
| [IInitializableAToken.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IInitializableAToken.sol)                   |                                                                                                                                   | 25   |
| [DataTypes.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/DataTypes.sol)                                         |                                                                                                                                   | 24   |
| [IUniswapV3Pool.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IUniswapV3Pool.sol)                               |                                                                                                                                   | 22   |
| [IERC721Permit.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IERC721Permit.sol)                                 |                                                                                                                                   | 14   |
| [IFlashLoanReceiver.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IFlashLoanReceiver.sol)                       |                                                                                                                                   | 14   |
| [IUniswapV2Factory.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IUniswapV2Factory.sol)                         |                                                                                                                                   | 12   |
| [ICreditDelegationToken.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/ICreditDelegationToken.sol)               |                                                                                                                                   | 11   |
| [IERC20.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IERC20.sol)                                               |                                                                                                                                   | 11   |
| [IPeripheryPayments.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IPeripheryPayments.sol)                       |                                                                                                                                   | 10   |
| [IPoolInitializer.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IPoolInitializer.sol)                           |                                                                                                                                   | 10   |
| [IWETH.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IWETH.sol)                                                 |                                                                                                                                   | 10   |
| [IUniswapV3SwapCallback.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IUniswapV3SwapCallback.sol)               |                                                                                                                                   | 8    |
| [IAaveOracle.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IAaveOracle.sol)                                     |                                                                                                                                   | 6    |
| [IScaledBalanceToken.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IScaledBalanceToken.sol)                     |                                                                                                                                   | 6    |
| [IPeripheryImmutableState.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IPeripheryImmutableState.sol)           |                                                                                                                                   | 5    |
| [IPriceOracle.sol](https://github.com/code-423n4/2023-08-goodentry/blob/main/contracts/interfaces/IPriceOracle.sol)                                   |                                                                                                                                   | 5    |
| SUM:                            

## Out of scope
All contracts and interfaces not explicitly mentioned above.

## Scoping Details 
- Public repository - https://github.com/GoodEntry-io/ge  
- Contracts are in scope?: 14  
- Total SLoC for these contracts?: 2482
- How many external imports are there?:  2
- How many separate interfaces and struct definitions are there for the contracts within scope?:  35
- Does most of your code generally use composition or inheritance?:  Composition
- How many external calls?: 5  
- What is the overall line coverage percentage provided by your tests?: 85%
- Is this an upgrade of an existing system?: No
- Check all that apply (e.g. timelock, NFT, AMM, ERC20, rollups, etc.): AMM, ERC-20 Token
- Is there a need to understand a separate part of the codebase / get context in order to audit this part of the protocol?:  Yes 
- Please describe required context: Requires understanding Aave LP and Uniswap  v3 positions  
- Does it use an oracle?:  Chainlink
- Describe any novel or unique curve logic or mathematical models your code uses: No new math.
- Is this either a fork of or an alternate implementation of another project?:  No
- Does it use a side-chain?: Yes. EVM-compatible side-chain.
- Describe any specific areas you would like addressed: Please try to steal funds or cause token value inflation
- Please list specific ERC20 that your protocol is anticipated to interact with:: USDC.e  (bridged USDC), wBTC, ARB, GMX
- Please list specific list of ERC721 that your protocol is anticipated to interact with: Uniswap V3 Positions
- Can you specify on which blockchain networks your smart contracts will be deployed?: Arbitrum
- Is any part of your implementation intended to conform to any EIP's?: TokenizableRange.sol and GeVault.sol are ERC20 compliant.


## Tests

The project uses Brownie as a testing framework. https://eth-brownie.readthedocs.io/en/stable/index.html

### Files
| File                                             | Unit Tests For                             |
| ------------------------------------------------ | ------------------------------------------ |
| test_RoeRouter.py                                | RoeRouter.sol                              |
| test_PositionManager.py                          | PositionManager/PositionManager.sol        |
| test_OptionsPositionManager.py                   | PositionManager/OptionsPositionManager.sol |
| test_RangeManager.py, test_RangeManager_WBTCUSDC | TokenisableRange.sol, RangeManager.sol     |
| test_GeVault.py                                  | GeVault.sol                                |

### Process

First, start a local mainnet-fork. You can use Alchemy or Infura or any archive node.

```bash
ganache-cli --port 8545 --gasLimit 12000000 --accounts 10 --hardfork istanbul --mnemonic brownie --fork https://eth-mainnet.g.alchemy.com/v2/aE_kYsizNYWhqZ18ryeMsl-JkWmCMgFj@16360000 --host 0.0.0.0
```

Then, run the tests,

```bash
brownie test
```

should return something like

```
tester:~/goodentry$ brownie test 
Brownie v1.19.3 - Python development framework for Ethereum

============================================================================================= test session starts ==============================================================================================
platform win32 -- Python 3.9.0, pytest-6.2.5, py-1.11.0, pluggy-1.0.0
rootdir: D:\projects\theta\code4rena-2023-08-goodentry
plugins: eth-brownie-1.19.3, hypothesis-6.27.3, forked-1.4.0, xdist-1.34.0, web3-5.31.3
collected 43 items
Attached to local RPC client listening at '127.0.0.1:8545'...

tests\test_GeVault.py.............
tests\test_OptionsPositionManager.py..........
tests\test_PositionManager.py.
tests\test_RangeManager.py .........
tests\test_RangeManager_WBTCUSDC.py.......
tests\test_RoeRouter.py...

=============================================================================================== warnings summary ===============================================================================================
c:\python39\lib\site-packages\brownie\network\main.py:44
  c:\python39\lib\site-packages\brownie\network\main.py:44: BrownieEnvironmentWarning: Development network has a block height of 16360001
    warnings.warn(

tests/test_OptionsPositionManager.py::test_unallowed_flashloan_call
tests/test_OptionsPositionManager.py::test_unallowed_flashloan_call
  c:\python39\lib\site-packages\eth_abi\codec.py:87: DeprecationWarning: abi.encode_abi() and abi.encode_abi_packed() are deprecated and will be removed in version 4.0.0 in favor of abi.encode() and abi.encode_packed(), respectively
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/warnings.html
================================================================================== 43 passed, 3 warnings in 338.45s (0:05:38) ==================================================================================
```


## Coverage 

```bash
brownie test
```


```
=================================================================================================== Coverage ===================================================================================================
contract: GeVault - 57.5%
    GeVault.checkSetApprove - 100.0%
    GeVault.getAdjustedBaseFee - 100.0%
    GeVault.deployAssets - 81.2%
    Address.functionCallWithValue - 75.0%
    ERC20._burn - 75.0%
    ERC20._mint - 75.0%
    GeVault.depositAndStash - 75.0%
    GeVault.getActiveTickIndex - 75.0%
    GeVault.rebalance - 75.0%
    SafeERC20._callOptionalReturn - 75.0%
    GeVault.removeFromTick - 70.8%
    GeVault.deposit - 67.9%
    GeVault.withdraw - 67.3%
    GeVault.poolMatchesOracle - 58.3%
    Address.verifyCallResult - 37.5%
    GeVault.<receive> - 25.0%
    ERC20._approve - 0.0%
    ERC20._transfer - 0.0%
    ERC20.decreaseAllowance - 0.0%
    ERC20.transferFrom - 0.0%
    GeVault.latestAnswer - 0.0%
    Ownable.transferOwnership - 0.0%

  contract: NullOracle - 100.0%
    NullOracle.getAssetPrice - 100.0%

  contract: OptionsPositionManager - 82.7%
    OptionsPositionManager.buyOptions - 100.0%
    OptionsPositionManager.calculateAndSendFee - 100.0%
    OptionsPositionManager.executeBuyOptions - 100.0%
    OptionsPositionManager.executeLiquidation - 100.0%
    OptionsPositionManager.executeOperation - 100.0%
    OptionsPositionManager.sellOptions - 100.0%
    PositionManager.PMWithdraw - 100.0%
    PositionManager.checkSetAllowance - 100.0%
    OptionsPositionManager.withdrawOptionAssets - 96.4%
    OptionsPositionManager.closeDebt - 87.9%
    OptionsPositionManager.close - 83.3%
    Address.functionCallWithValue - 75.0%
    OptionsPositionManager.checkExpectedBalances - 75.0%
    OptionsPositionManager.getTargetAmountFromOracle - 75.0%
    OptionsPositionManager.liquidate - 75.0%
    OptionsPositionManager.swapTokensForExactTokens - 75.0%
    OptionsPositionManager.withdrawOptions - 75.0%
    SafeERC20._callOptionalReturn - 75.0%
    PositionManager.cleanup - 50.0%
    Address.verifyCallResult - 37.5%

  contract: RangeManager - 88.6%
    RangeManager.generateRange - 100.0%
    RangeManager.transferAssetsIntoStep - 100.0%
    RangeManager.removeFromStep - 93.8%
    RangeManager.checkNewRange - 91.7%
    RangeManager.cleanup - 91.7%
    Ownable.transferOwnership - 0.0%

  contract: Test_OptionsPositionManager - 12.6%
    OptionsPositionManager.getTargetAmountFromOracle - 100.0%
    OptionsPositionManager.swapTokensForExactTokens - 91.7%
    PositionManager.checkSetAllowance - 75.0%
    OptionsPositionManager.buyOptions - 0.0%
    OptionsPositionManager.calculateAndSendFee - 0.0%
    OptionsPositionManager.checkExpectedBalances - 0.0%
    OptionsPositionManager.close - 0.0%
    OptionsPositionManager.closeDebt - 0.0%
    OptionsPositionManager.executeBuyOptions - 0.0%
    OptionsPositionManager.executeLiquidation - 0.0%
    OptionsPositionManager.executeOperation - 0.0%
    OptionsPositionManager.liquidate - 0.0%
    OptionsPositionManager.sellOptions - 0.0%
    OptionsPositionManager.withdrawOptionAssets - 0.0%
    OptionsPositionManager.withdrawOptions - 0.0%
    PositionManager.PMWithdraw - 0.0%
    PositionManager.cleanup - 0.0%

  contract: TickMath - 86.5%
    TickMath.getSqrtRatioAtTick - 89.2%
    TickMath.getTickAtSqrtRatio - 72.5%

  contract: TokenisableRange - 67.0%
    ERC20.transferFrom - 100.0%
    TokenisableRange.init - 100.0%
    TokenisableRange.initProxy - 100.0%
    ERC20._approve - 87.5%
    ERC20._burn - 87.5%
    TokenisableRange.returnExpectedBalance - 87.5%
    ERC20._transfer - 83.3%
    LiquidityAmounts.getAmountsForLiquidity - 81.7%
    ERC20._mint - 75.0%
    LiquidityAmounts.getAmount0ForLiquidity - 50.0%
    LiquidityAmounts.getAmount1ForLiquidity - 50.0%
    TokenisableRange.getValuePerLPAtPrice - 50.0%
    TokenisableRange.withdraw - 50.0%
    TokenisableRange.deposit - 49.6%
    FullMath.mulDiv - 25.8%
    ERC20.decreaseAllowance - 0.0%

  contract: UpgradeableBeacon - 100.0%
    Ownable.transferOwnership - 100.0%
```
