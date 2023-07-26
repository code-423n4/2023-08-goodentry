import pytest, brownie
import math


# CONSTANTS
NULL = "0x0000000000000000000000000000000000000000"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
TREASURY="0x50101017adf9D2d06C395471Bc3D6348589c3b97" # random empty
ROUTER="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
ROUTERV3="0xE592427A0AEce92De3Edee1F18E0157C05861564"
# LPAD for btc 0xe7f6F6Cd1Be8313a05e0E38bA97B2A5Dfed7616d - for weth "0x01b76559D512Fa28aCc03630E8954405BcBB1E02"
LENDING_POOL_ADDRESSES_PROVIDER = "0x01b76559D512Fa28aCc03630E8954405BcBB1E02" 

# Careful: ticker range now in middle of range, testing ticker
RANGE_LIMITS = [500, 1000, 2000, 2500, 5000]

@pytest.fixture(scope="module", autouse=True)
def weth(interface, accounts):
  # Claim WETH from MATIC-Aave pool
  aaveWETH = accounts.at("0x28424507fefb6f7f8e9d3860f56504e4e5f5f390", force=True)
  weth = interface.ERC20(WETH, owner=aaveWETH)
  yield weth

@pytest.fixture(scope="module", autouse=True)
def usdc(interface, accounts):
  # Claim USDC from Stargate stake account
  stargate = accounts.at("0x1205f31718499dBf1fCa446663B532Ef87481fe1", force=True)
  usdc  = interface.ERC20(USDC, owner=stargate)
  yield usdc


@pytest.fixture(scope="module", autouse=True)
def router(interface):
  router = interface.IUniswapV2Router01(ROUTER)
  yield router
  
@pytest.fixture(scope="module", autouse=True)
def routerV3(interface):
  routerV3 = interface.ISwapRouter(ROUTERV3)
  yield routerV3
  

# No isolation when testing uniswap as it will cause reentrancy reverts
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

  
@pytest.fixture(scope="module", autouse=True)
def lendingPool(interface, accounts):
  lpadd = interface.ILendingPoolAddressesProvider(LENDING_POOL_ADDRESSES_PROVIDER)
  poolAdmin = accounts.at(lpadd.getPoolAdmin(), force=True)
  try:
    lpadd.setLendingPoolImpl("0x09add1BC0CaC5FD269CE5eceA034e218bF16FA76", {"from": poolAdmin}) # Set to correct implementation
  except: 
    pass
  configurator = interface.ILendingPoolConfigurator(lpadd.getLendingPoolConfigurator());
  lendingPool = interface.ILendingPool(lpadd.getLendingPool())
  yield lendingPool
    
@pytest.fixture(scope="module", autouse=True)
def oracle(interface, accounts):
  lpAdd = interface.ILendingPoolAddressesProvider(LENDING_POOL_ADDRESSES_PROVIDER)
  oracle = interface.IAaveOracle( lpAdd.getPriceOracle() )
  yield oracle


@pytest.fixture(scope="module", autouse=True)
def config(interface, accounts):
  lpAdd = interface.ILendingPoolAddressesProvider(LENDING_POOL_ADDRESSES_PROVIDER)
  config = interface.ILendingPoolConfigurator(lpAdd.getLendingPoolConfigurator() )
  yield config
  
  
# Call to seed accounts before isolation tests
@pytest.fixture(scope="module", autouse=True)
def seed_accounts( weth, usdc, user, owner, lendingPool, accounts):
  try: 
    AAVE_WETH = "0x030ba81f1c18d280636f32af80b9aad02cf0854e"
    AAVE_USDC = "0xbcca60bb61934080951369a648fb03df4f96263c"
    aaveUSDC = accounts.at(AAVE_USDC, force=True)
    aaveWETH = accounts.at(AAVE_WETH, force=True)

    weth.approve(lendingPool, 2**256-1, {"from": aaveWETH})
    weth.transfer(owner, 5e18, {"from": aaveWETH})
    lendingPool.deposit(weth, 30e18, owner, 0, {"from": aaveWETH}) 
    lendingPool.deposit(weth, 30e18, user, 0, {"from": aaveWETH}) 

    usdc.approve(lendingPool, 2**256-1, {"from": aaveUSDC})
    usdc.transfer(owner, 5e10, {"from": aaveUSDC})
    lendingPool.deposit(usdc, 30e10, owner, 0, {"from": aaveUSDC}) 
    lendingPool.deposit(usdc, 30e10, user, 0, {"from": aaveUSDC}) 

  except Exception as e:
    print(e)

  
@pytest.fixture(scope="module", autouse=True)
def contracts(owner, Strings, TickMath, TokenisableRange, UpgradeableBeacon, RangeManager, lendingPool, router, weth, usdc):
  Strings.deploy({"from": owner})
  TickMath.deploy({"from": owner})
  tr = TokenisableRange.deploy({"from": owner})
  trb = UpgradeableBeacon.deploy(tr, {"from": owner})
  r = RangeManager.deploy(lendingPool, usdc, weth, {"from": owner})
  yield tr, trb, r


# calc range values for uni v3: https://docs.google.com/spreadsheets/d/1EXqXeXysknbib3_WbUB-lGGknBjxJvt4/edit#gid=385415845
# OR return values from https://app.uniswap.org/#/add/ETH/0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48/3000?chain=mainnet&maxPrice=2000&minPrice=1600
@pytest.fixture(scope="module", autouse=True)
def liquidityRatio(interface, usdc, weth):
  def liqRatio(rangeLow, rangeHigh):
    pool = interface.IUniswapV3Factory("0x1F98431c8aD98523631AE4a59f267346ea31F984").getPool(usdc, weth, 3000)
    sqrtPriceX96 = interface.IUniswapV3Pool(pool).slot0()[0]
    price = ( 2 ** 192 / sqrtPriceX96 ** 2 ) * 1e12 # 1e12 because decimal difference between WETH and USDC
    if price < rangeLow: price = rangeLow
    if price > rangeHigh: price = rangeHigh
    priceSqrt = math.sqrt( math.pow(1.0001, -math.log(math.sqrt(price)) * 2 / math.log(1.0001)))
    priceLowSqrt = math.sqrt( math.pow(1.0001, -math.log(math.sqrt(rangeLow)) * 2 / math.log(1.0001)))
    priceHighSqrt = math.sqrt( math.pow(1.0001, -math.log(math.sqrt(rangeHigh)) * 2 / math.log(1.0001)))
    if priceSqrt == priceLowSqrt: return 0, 1e18 / rangeLow
    relation = (priceSqrt-priceHighSqrt) / ( (1/priceSqrt) - (1/priceLowSqrt) )
    lpAmount = 1
    usdAmount = lpAmount / ( 1 + relation * price ) 
    ethAmount = relation * usdAmount
    return usdAmount * 1e6, ethAmount * 1e18
  yield liqRatio


# Check if 2 vaslues are within 1%
def nearlyEqual(value0, value1):
  if (value1 == 0): return value1 == value0
  else: return abs (value0-value1) / value1 < 0.01



# Test tickers: create a ticker below current WETH price and test general functionalities
def test_TT_tickerBelow(accounts, owner, lendingPool, weth, usdc, user, interface, router, routerV3, oracle, TokenisableRange, liquidityRatio):
  tr = TokenisableRange.deploy({"from": owner})
  
  with brownie.reverts("!InitLP"): tr.init(1e6, 0, {"from": owner})
  with brownie.reverts("Invalid oracle"):
    tr.initProxy(NULL, usdc, weth, RANGE_LIMITS[0]*1e10, RANGE_LIMITS[1]*1e10, RANGE_LIMITS[0], RANGE_LIMITS[1], True)
  tr.initProxy(oracle, usdc, weth, RANGE_LIMITS[0]*1e10, RANGE_LIMITS[1]*1e10, RANGE_LIMITS[0], RANGE_LIMITS[1], True)
  
  with brownie.reverts("!InitProxy"): 
    tr.initProxy(oracle, usdc, weth, RANGE_LIMITS[1]*1e10, RANGE_LIMITS[2]*1e10, RANGE_LIMITS[1], RANGE_LIMITS[2], True)
  
  with brownie.reverts("TR Closed"): tr.deposit(1e6, 0, {"from": owner})
  usdc.approve(tr, 2**256-1, {"from": owner})
  weth.approve(tr, 2**256-1, {"from": owner})
  
  assert tr.getValuePerLPAtPrice(0, 0) == 0
  
  with brownie.reverts("Unallowed call"): tr.init(1e6, 0, {"from": user}) # init can only be called by same caller as initProxy
  with brownie.reverts(): tr.init(0, 1e16, {"from": owner}) # Uniswap throws: ETH in an USDC only position
  tr.init(1e6, 0, {"from": owner})
  assert tr.balanceOf(owner) == 1e18
  print("Ticker", tr.name(), tr.symbol())
  liquidity = tr.liquidity()
  print('liquidity', tr.liquidity())
  print('underlying', tr.getTokenAmounts(tr.balanceOf(owner)))
    
  # various stuff as coverage is below ratio becuase of untested libraries
  with brownie.reverts("ERC20: approve to the zero address"): tr.approve("0x0000000000000000000000000000000000000000", 1, {"from": owner})
  tr.approve(user, 1, {"from": owner})
  with brownie.reverts("ERC20: transfer to the zero address"): tr.transferFrom(owner, "0x0000000000000000000000000000000000000000", 1, {"from": user})
  with brownie.reverts("ERC20: transfer amount exceeds allowance"): tr.transferFrom(owner, user, 2, {"from": user})
  
  with brownie.reverts(): tr.deposit(0, 1e16, {"from": owner})
  tr.deposit(3e6, 0, {"from": owner}) 
  assert nearlyEqual( tr.balanceOf(owner), 4e18)
  assert nearlyEqual( tr.liquidity(), 4 * liquidity )
  
  tr.approve(user, 2**256-1, {"from": owner})
  assert tr.allowance(owner, user) == 2**256-1
  
  usdBal = usdc.balanceOf(owner)
  tr.withdraw( tr.balanceOf(owner) / 2, 0, 0, {"from": owner})
  # usdc balance increased from the 2e6 USD as we withdraw half the liquidity, modulo 1 unit of rounding error
  assert abs(usdBal + 2e6 - usdc.balanceOf(owner)) <= 1 
  
  print('liquidity', tr.liquidity())
  print('underlying', tr.getTokenAmounts(tr.balanceOf(owner)))
  assert nearlyEqual (2 * liquidity, tr.liquidity())
  
  with brownie.reverts(): tr.withdraw( 0, 0, 0, {"from": owner})
  with brownie.reverts("ERC20: burn amount exceeds balance"): tr.withdraw( tr.balanceOf(owner)+1, 0, 0, {"from": owner})
  tr.withdraw( tr.balanceOf(owner), 0, 0, {"from": owner})
  with brownie.reverts("TR Closed"): tr.deposit(1e6, 0, {"from": owner})
  assert tr.liquidity() == 0
  
  
# Create a Ranger range with price within boundaries (spot price: 1268, lower bound 500, higher bound 5000)
def test_TR(accounts, owner, lendingPool, weth, usdc, user, interface, router, routerV3, oracle, TokenisableRange, liquidityRatio):
  usdAmount, ethAmount = liquidityRatio(RANGE_LIMITS[0], RANGE_LIMITS[4]) 
  tr = TokenisableRange.deploy({"from": owner})
  tr.initProxy(oracle, usdc, weth, RANGE_LIMITS[0]*1e10, RANGE_LIMITS[4]*1e10, "500", "5000", False)
  
  with brownie.reverts("!InitProxy"): 
    tr.initProxy(oracle, usdc, weth, 500*1e10, 5000*1e10, "500", "1500", True)
        
  usdc.approve(tr, 2**256-1, {"from": owner})  
  weth.approve(tr, 2**256-1, {"from": owner})
  with brownie.reverts(): tr.init(0, 1e16, {"from": owner}) # Uniswap throws: unbalanced liquidity added
  tr.init(usdAmount, ethAmount, {"from": owner})
  
  #test liquidity
  liq0, liq1 = tr.getTokenAmounts(tr.balanceOf(owner))
  assert abs(liq0 - usdAmount ) <= 10 and abs(liq1 - ethAmount) <= 1e13 # less than 10 unit diff from rounding, usd decimals = 6 and eth decimals = 18
  
  with brownie.reverts(): tr.deposit(0, 1e16, {"from": owner})
  tr.deposit(usdAmount, ethAmount, {"from": owner})

  # withdraw with no fees in pool
  tr.withdraw( tr.balanceOf(owner)/2, 0, 0, {"from": owner})
  tr.claimFee()  #no fees to claim
  
  # create fees by swapping
  usdc.approve(routerV3, 2**256-1, {"from": owner} )
  weth.approve(routerV3, 2**256-1, {"from": owner} )
  routerV3.exactInputSingle([usdc, weth, 500, owner, 2e20, 1e10, 0, 0], {"from": owner})
  routerV3.exactInputSingle([weth, usdc, 500, owner, 2e20, 1e15, 0, 0], {"from": owner})
  treasury = tr.treasury()
  usdcTreasuryBal = usdc.balanceOf(treasury)
  wethTreasuryBal = weth.balanceOf(treasury)
  print('treasury bals', usdcTreasuryBal, wethTreasuryBal)
  # check fees
  tr.claimFee()
  print(tr.fee0(), tr.fee1())
  usdcTreasuryBal = usdc.balanceOf(treasury)
  wethTreasuryBal = weth.balanceOf(treasury)
  print('treasury bals', usdcTreasuryBal, wethTreasuryBal)
  
  with brownie.reverts("ERC20: burn amount exceeds balance"): tr.withdraw( tr.balanceOf(owner)+1, 0, 0, {"from": owner})
  tr.withdraw( tr.balanceOf(owner)/2, 0, 0, {"from": owner})
  tr.withdraw( tr.balanceOf(owner), 0, 0, {"from": owner})
  # should be left with very little, try compounding fees
  tr.claimFee()



# Check that token inflation isnt possible by depositing assets in the underlying NFT
def test_TR_inflation(accounts, owner, lendingPool, weth, usdc, user, interface, router, routerV3, oracle, TokenisableRange, liquidityRatio):
  usdAmount, ethAmount = liquidityRatio(RANGE_LIMITS[0], RANGE_LIMITS[4]) 
  tr = TokenisableRange.deploy({"from": owner})
  tr.initProxy(oracle, usdc, weth, RANGE_LIMITS[0]*1e10, RANGE_LIMITS[4]*1e10, "500", "5000", False)
        
  usdc.approve(tr, 2**256-1, {"from": owner})  
  weth.approve(tr, 2**256-1, {"from": owner})
  tr.init(usdAmount, ethAmount, {"from": owner})
  
  price = tr.latestAnswer()
  amount0, amount1 = tr.getTokenAmounts(tr.totalSupply())
  underlyingValue = amount0 * oracle.getAssetPrice(usdc) / 1e6 + amount1 * oracle.getAssetPrice(weth) / 1e18
  
  #deposit in the NFT directly 
  nft = interface.INonfungiblePositionManager("0xC36442b4a4522E871399CD717aBDD847Ab11FE88")

  weth.approve(nft, 2**256-1, {"from": owner})
  usdc.approve(nft, 2**256-1, {"from": owner})
  # bypass TR to add liquidity, doubling the total amount
  nft.increaseLiquidity([tr.tokenId(), usdAmount, ethAmount, 0, 0, 1e12], {"from":owner})
  
  price2 = tr.latestAnswer()
  amount0, amount1 = tr.getTokenAmounts(tr.totalSupply())
  underlyingValue2 = amount0 * oracle.getAssetPrice(usdc) / 1e6 + amount1 * oracle.getAssetPrice(weth) / 1e18
  # price shouldnt have changed despite the deposit of tokens inside the NFT
  assert price == price2
  

# Test that ranger correctly prevents invalid ranges and overlapping
def test_ranger_overlap(user, owner, RangeManager, lendingPool, usdc, weth, router, TokenisableRange, UpgradeableBeacon):
  r = RangeManager.deploy(lendingPool, usdc, weth, {"from": owner})
  tr = TokenisableRange.deploy({"from": owner})
  trb = UpgradeableBeacon.deploy(tr, {"from": owner})
  
  with brownie.reverts("Ownable: caller is not the owner"): r.generateRange(2000 * 1e10, 1600 * 1e10, 'XXX', 'YYY', trb, {"from": user})
  with brownie.reverts("Invalid beacon"): r.generateRange(2000 * 1e10, 1600 * 1e10, 'XXX', 'YYY', NULL, {"from": owner})
  with brownie.reverts("Range invalid"): r.generateRange(2000 * 1e10, 1600 * 1e10, 'XXX', 'YYY', trb, {"from": owner})
  r.generateRange(1200 * 1e10, 1600 * 1e10, 'XXX', 'YYY', trb, {"from": owner})
  with brownie.reverts("Range overlap"): r.generateRange(1000 * 1e10, 1400 * 1e10, 'XXX', 'YYY', trb, {"from": owner})
  with brownie.reverts("Range overlap"): r.generateRange(1400 * 1e10, 1800 * 1e10, 'XXX', 'YYY', trb, {"from": owner})
  with brownie.reverts("Range overlap"): r.generateRange(1400 * 1e10, 1500 * 1e10, 'XXX', 'YYY', trb, {"from": owner})


# Create tickers and rangers with various prices through the Range manager, and add them to the lending pool for further testing
@pytest.fixture(scope="module", autouse=True)
def prep_ranger(accounts, owner, timelock, lendingPool, weth, usdc, user, interface, router, oracle, config, contracts, TokenisableRange,seed_accounts,liquidityRatio):
  tr, trb, r = contracts

  ranges = [ [RANGE_LIMITS[0], RANGE_LIMITS[1]], [RANGE_LIMITS[1], RANGE_LIMITS[2]], [RANGE_LIMITS[2], RANGE_LIMITS[3]] ]
  for i in ranges:
    r.generateRange( i[0]*1e10, i[1]*1e10, i[0], i[1], trb, {"from": owner})
    
  numRanges = r.getStepListLength()

  # Approve rangeManager for init
  weth.approve(r, 2**256-1, {"from": owner})
  usdc.approve(r, 2**256-1, {"from": owner})

  for i in range(numRanges):
    usdAmount, ethAmount = liquidityRatio( ranges[i][0], ranges[i][1])  
    r.initRange(r.tokenisedRanges(i), usdAmount, ethAmount, {"from": owner})
    usdAmount, ethAmount = liquidityRatio( (ranges[i][0]+ranges[i][1])/2,(ranges[i][0]+ranges[i][1])/2 + 1)
    r.initRange(r.tokenisedTicker(i), usdAmount, ethAmount, {"from": owner})  
  
  # Load all into Oracle
  addresses = [r.tokenisedRanges(i) for i in range(3)] + [r.tokenisedTicker(i) for i in range(3)]
  oracle.setAssetSources( addresses, addresses, {"from": timelock}) 

  # Load all into Lending Pool
  theta_A = "0x78b787C1533Acfb84b8C76B7e5CFdfe80231Ea2D" # matic "0xb54240e3F2180A0E14CE405A089f600dc2D8457c"
  theta_stbDebt = "0x8B6Ab2f071b27AC1eEbFfA973D957A767b15b2DB" # matic "0x92ED25161bb90eb0026e579b60B8D96eE3b7A15F"
  theta_varDebt = "0xB19Dd5DAD35af36CF2D80D1A9060f1949b11fCb0" # matic "0x51b89b9e24bc85d6756571032B8bf5660Bf6FbE5"
  theta_100bps_fixed = "0xfAdB757A7BC3031285417d7114EFD58598E21d79" # "0xEdFbbeDdc3CB3271fd60E90E184B151C76Cd88aB"

  reserves = []
  for i in addresses:
      sym = TokenisableRange.at(i).symbol()
      name = TokenisableRange.at(i).name()
      reserves.append( [theta_A, theta_stbDebt, theta_varDebt, 18, theta_100bps_fixed, i, owner.address, NULL, sym, "Roe " + name, "roe"+sym, "Roe variable debt bearing " + name, "vd"+sym, "Roe stable debt bearing " + name, "sd" + sym, ""] )
  lpadd = interface.ILendingPoolAddressesProvider(LENDING_POOL_ADDRESSES_PROVIDER)
  poolAdmin = accounts.at(lpadd.getPoolAdmin(), force=True)
  for i in reserves: config.batchInitReserve([i], {"from": poolAdmin})

  # Enable as collateral
  for i in addresses:
    config.configureReserveAsCollateral(i, 9250, 9500, 10300, {"from": poolAdmin})



# Check balances and price
def test_ranges_values(owner, lendingPool, weth, usdc, user, interface, oracle, contracts, TokenisableRange, prep_ranger):
  tr, trb, r = contracts
  
  # expect added balance in 1st ticker to be the same as balance estimate
  (uBal, eBal) = TokenisableRange.at(r.tokenisedTicker(0)).returnExpectedBalance(0, 0) 
  assert eBal == 0 and round( (10e6 - uBal) / 10e6 ) <= 1 # allow a 1 rounding error
  # above a range, price and balance should remain constant as it contains USDC only
  for i in range(3):
    assert TokenisableRange.at(r.tokenisedTicker(i)).returnExpectedBalance(0, 3000e8) == TokenisableRange.at(r.tokenisedTicker(i)).returnExpectedBalance(1e8, 4000e8)
    assert TokenisableRange.at(r.tokenisedTicker(i)).getValuePerLPAtPrice(1e8, 3000e8) == TokenisableRange.at(r.tokenisedTicker(i)).getValuePerLPAtPrice(1e8, 4000e8)    
    assert TokenisableRange.at(r.tokenisedRanges(i)).returnExpectedBalance(1e8, 3000e8) == TokenisableRange.at(r.tokenisedRanges(i)).returnExpectedBalance(1e8, 4000e8)
    assert TokenisableRange.at(r.tokenisedRanges(i)).getValuePerLPAtPrice(1e8, 3000e8) == TokenisableRange.at(r.tokenisedRanges(i)).getValuePerLPAtPrice(1e8, 4000e8)
  # below a range, balance remains constant
  for i in range(3):
    assert TokenisableRange.at(r.tokenisedRanges(i)).returnExpectedBalance(0, 300e8) == TokenisableRange.at(r.tokenisedRanges(i)).returnExpectedBalance(0, 400e8)
  # above a tick should be usdc only, below should be weth only
  assert TokenisableRange.at(r.tokenisedTicker(0)).returnExpectedBalance(1e8, 3000e8)[1] == 0 # below, no usdc# above, no weth
  assert TokenisableRange.at(r.tokenisedTicker(0)).returnExpectedBalance(1e8, 300e8)[0] == 0 
  

# Test invalid step
def test_ranger_invalidstep(owner, lendingPool, weth, usdc, user, interface, capsys, oracle, contracts, TokenisableRange, prep_ranger):
  tr, trb, r = contracts
  with brownie.reverts("Invalid step"): r.removeAssetsFromStep(10, {"from":owner}) 


# Test deposit/withdraw in ticker through RangeManager (which automatically deposits in the lendingPool)
def test_deposit_withdraw_ticker(timelock, lendingPool, weth, usdc, user, interface, oracle, contracts, prep_ranger):
  tr, trb, r = contracts
  lendingPool.PMAssign(r, {"from": timelock})
  
  # Deposit/withdraw in ticker below 
  usdAmount = 10e6
  r.transferAssetsIntoTickerStep(0, usdAmount, 0, {"from":user}) 
  t = interface.IAToken( lendingPool.getReserveData(r.tokenisedTicker(0))[7] )
  print( oracle.getAssetPrice(r.tokenisedTicker(0)) * t.balanceOf(user) / 1e18, oracle.getAssetPrice(usdc) * usdAmount / 1e6)
  assert nearlyEqual(
    oracle.getAssetPrice(r.tokenisedTicker(0)) * t.balanceOf(user) / 1e18, 
    oracle.getAssetPrice(usdc) * usdAmount / 1e6
  )
  r.removeAssetsFromStep(0, {"from":user})
  assert t.balanceOf(user) == 0  
  
  # Deposit/withdraw in ticker above 
  ethAmount = 1e17
  r.transferAssetsIntoTickerStep(2, 0, ethAmount, {"from":user})
  t = interface.IAToken( lendingPool.getReserveData(r.tokenisedTicker(2))[7] )
  assert nearlyEqual(
    oracle.getAssetPrice(r.tokenisedTicker(2)) * t.balanceOf(user), 
    oracle.getAssetPrice(weth) * ethAmount
  )
  r.removeAssetsFromStep(2, {"from":user})
  assert t.balanceOf(user) == 0


# Test deposit/withdraw in ranger through RangeManager
def test_deposit_withdraw_ranger(owner, timelock, lendingPool, weth, usdc, user, interface, oracle, contracts, prep_ranger, liquidityRatio):
  tr, trb, r = contracts
  lendingPool.PMAssign(r, {"from": timelock})

  usdAmount, ethAmount = liquidityRatio(RANGE_LIMITS[1], RANGE_LIMITS[2])
  print('test_ranger_deposit_withdraw, amounts', usdAmount, ethAmount)
  
  # Deposit/withdraw in ranger above
  step = 2
  r.transferAssetsIntoRangerStep(step, 0, ethAmount, {"from":user})
  t = interface.IAToken( lendingPool.getReserveData(r.tokenisedRanges(step))[7] )
  assert nearlyEqual( 
    oracle.getAssetPrice(r.tokenisedRanges(step)) * t.balanceOf(user) / 1e18, 
    oracle.getAssetPrice(weth) * ethAmount / 1e18
  )
  r.removeAssetsFromStep(step, {"from":user})
  assert t.balanceOf(user) == 0
  
  # Deposit/withdraw in ranger below
  step = 0
  r.transferAssetsIntoRangerStep(step, usdAmount, 0, {"from":user})
  t = interface.IAToken( lendingPool.getReserveData(r.tokenisedRanges(step))[7] )
  assert nearlyEqual( 
    oracle.getAssetPrice(r.tokenisedRanges(step)) * t.balanceOf(user) / 1e18, 
    oracle.getAssetPrice(usdc) * usdAmount / 1e6
  )
  r.removeAssetsFromStep(step, {"from":user})
  assert t.balanceOf(user) == 0  
  
  # Deposit/withdraw in active range
  step = 1
  t = interface.IAToken( lendingPool.getReserveData(r.tokenisedRanges(step))[7] )
  r.transferAssetsIntoRangerStep(step, usdAmount, ethAmount, {"from":user})
  ownerRoeBal = t.balanceOf(owner)
  r.transferAssetsIntoRangerStep(step, usdAmount, ethAmount, {"from":user})
  # transferAssetsIntoRangerStep withdraws previously exisiting liquidity before adding new liquidity and owner balance shouldn't change
  assert ownerRoeBal == t.balanceOf(owner)
  
  assert nearlyEqual( 
    oracle.getAssetPrice(r.tokenisedRanges(step)) * t.balanceOf(user) / 1e18, 
    oracle.getAssetPrice(weth) * ethAmount / 1e18 + oracle.getAssetPrice(usdc) * usdAmount / 1e6
  )
  r.removeAssetsFromStep(step, {"from":user})
  assert t.balanceOf(user) == 0


# Test upgrading the TokenisableRange proxy
def test_proxy_upgrade(owner, timelock, lendingPool, weth, usdc, user, interface, contracts, TokenisableRange, prep_ranger, liquidityRatio):
  tr, trb, r = contracts
  lendingPool.PMAssign(r, {"from": timelock})
  usdAmount, ethAmount = liquidityRatio(RANGE_LIMITS[1], RANGE_LIMITS[2])
  r.transferAssetsIntoRangerStep(1, usdAmount, ethAmount, {"from":owner})
  ownerBal = TokenisableRange.at(r.tokenisedRanges(1)).balanceOf(owner)
  ownerRoeBal = interface.IAToken( lendingPool.getReserveData(r.tokenisedRanges(1))[7] ).balanceOf(owner)

  tr2 = TokenisableRange.deploy({"from": owner})
  with brownie.reverts("Ownable: new owner is the zero address"): 
    trb.transferOwnership("0x0000000000000000000000000000000000000000", {"from": owner})
  trb.transferOwnership(timelock, {"from": owner})
  trb.upgradeTo(tr2, {"from": timelock})

  assert ownerRoeBal == interface.IAToken( lendingPool.getReserveData(r.tokenisedRanges(1))[7] ).balanceOf(owner)
  assert ownerBal == TokenisableRange.at(r.tokenisedRanges(1)).balanceOf(owner)
  
  # transferAssetsIntoRangerStep withdraws previously exisiting liquidity before adding new liquidity
  r.transferAssetsIntoRangerStep(1, usdAmount, ethAmount, {"from":owner})
  assert ownerRoeBal == interface.IAToken( lendingPool.getReserveData(r.tokenisedRanges(1))[7] ).balanceOf(owner)
  
  t = TokenisableRange.at(r.tokenisedRanges(1))
  usdc.approve(t, 2**256-1, {"from": owner})
  weth.approve(t, 2**256-1, {"from": owner})
  TokenisableRange.at(r.tokenisedRanges(1)).deposit(usdAmount, ethAmount, {"from": owner})
  assert TokenisableRange.at(r.tokenisedRanges(1)).balanceOf(owner) == ownerBal * 2