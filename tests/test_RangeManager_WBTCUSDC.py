import pytest, brownie
from brownie import network
import math


# CONSTANTS
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WBTC = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
TREASURY="0x50101017adf9D2d06C395471Bc3D6348589c3b97" # random empty
ROUTER="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
ROUTERV3="0xE592427A0AEce92De3Edee1F18E0157C05861564"
# LPAD for btc 0xe7f6F6Cd1Be8313a05e0E38bA97B2A5Dfed7616d - for weth "0x01b76559D512Fa28aCc03630E8954405BcBB1E02"
LENDING_POOL_ADDRESSES_PROVIDER = "0xe7f6F6Cd1Be8313a05e0E38bA97B2A5Dfed7616d" 
NULL = "0x0000000000000000000000000000000000000000"

RANGE_LIMITS = [8000, 14000, 24000, 28000]


@pytest.fixture(scope="module", autouse=True)
def weth(interface, accounts):
  # Claim WETH from MATIC-Aave pool
  aaveWETH = accounts.at("0x28424507fefb6f7f8e9d3860f56504e4e5f5f390", force=True)
  weth = interface.ERC20(WETH, owner=aaveWETH)
  yield weth

@pytest.fixture(scope="module", autouse=True)
def wbtc(interface, accounts):
  aaveWBTC = accounts.at("0x9ff58f4ffb29fa2266ab25e75e2a8b3503311656", force=True)
  wbtc = interface.ERC20(WBTC, owner=aaveWBTC)
  yield wbtc


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
  
#@pytest.fixture(scope="module", autouse=True)
#def pdp(interface):
#  pdp = interface.IProtocolDataProvider("0xC68A4F7764f5219f250614d5647258a17A51a6c7") # matic "0xeA1e8259F26987F1C0E2E6b3deA16455EAAC2eAB")
#  yield pdp


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
def seed_accounts(interface, weth, wbtc, usdc, user, owner, lendingPool, accounts):
  #try: 
    lotsTokens = accounts.at("0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc", force=True)
    lotsWBTC = accounts.at("0x9ff58f4ffb29fa2266ab25e75e2a8b3503311656", force=True)
    usdc.approve(lendingPool, 2**256-1, {"from": lotsTokens})
    usdc.transfer(owner, 5e10, {"from": lotsTokens})
    lendingPool.deposit(usdc, 30e10, owner, 0, {"from": lotsTokens}) 
    lendingPool.deposit(usdc, 30e10, user, 0, {"from": lotsTokens}) 
    wbtc.approve(lendingPool, 2**256-1, {"from": lotsWBTC})
    wbtc.transfer(owner, 5e8, {"from": lotsWBTC})
    lendingPool.deposit(wbtc, 30e8, owner, 0, {"from": lotsWBTC}) 
    lendingPool.deposit(wbtc, 30e8, user, 0, {"from": lotsWBTC}) 
  #except Exception as e:
    #print(e)
  
@pytest.fixture(scope="module", autouse=True)
def contracts(owner, Strings, TickMath, TokenisableRange, UpgradeableBeacon, RangeManager, lendingPool, router, wbtc, usdc):
  Strings.deploy({"from": owner})
  TickMath.deploy({"from": owner})
  tr = TokenisableRange.deploy({"from": owner})
  trb = UpgradeableBeacon.deploy(tr, {"from": owner})
  r = RangeManager.deploy(lendingPool, wbtc, usdc, {"from": owner})
  yield tr, trb, r


# calc range values for uni v3: https://docs.google.com/spreadsheets/d/1EXqXeXysknbib3_WbUB-lGGknBjxJvt4/edit#gid=385415845
# OR return values from https://app.uniswap.org/#/add/ETH/0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48/3000?chain=mainnet&maxPrice=2000&minPrice=1600
@pytest.fixture(scope="module", autouse=True)
def liquidityRatio(interface, usdc, wbtc):
  def liqRatio(rangeLow, rangeHigh):
    pool = interface.IUniswapV3Factory("0x1F98431c8aD98523631AE4a59f267346ea31F984").getPool(usdc, wbtc, 3000)
    slot0 = interface.IUniswapV3Pool(pool).slot0()
    #print('pool', pool, slot0)
    sqrtPriceX96 = slot0[0]
    price = ( 2 ** 192 / sqrtPriceX96 ** 2 ) / 1e2 # 1e2 because decimal difference between Wbtc and USDC
    print('price', price, 'rL', rangeLow, 'rH', rangeHigh)
    if price < rangeLow: price = rangeLow
    if price > rangeHigh: price = rangeHigh
    priceSqrt = math.sqrt( math.pow(1.0001, -math.log(math.sqrt(price)) * 2 / math.log(1.0001)))
    priceLowSqrt = math.sqrt( math.pow(1.0001, -math.log(math.sqrt(rangeLow)) * 2 / math.log(1.0001)))
    priceHighSqrt = math.sqrt( math.pow(1.0001, -math.log(math.sqrt(rangeHigh)) * 2 / math.log(1.0001)))
    if priceSqrt == priceLowSqrt: 
      return 1e2 / rangeLow, 0
    relation = (priceSqrt-priceHighSqrt) / ( (1/priceSqrt) - (1/priceLowSqrt) )
    lpAmount = 0.1
    btcAmount = lpAmount / ( 1 + relation * price ) 
    usdAmount = relation * btcAmount
    return usdAmount * 1e6, btcAmount * 1e8
  yield liqRatio


def test_TT_tickerBelow(accounts, owner, lendingPool, wbtc, usdc, user, interface, router, routerV3, oracle, TokenisableRange, liquidityRatio):
  tr = TokenisableRange.deploy({"from": owner})
  tr.initProxy(oracle, wbtc, usdc, 1e10/RANGE_LIMITS[3], 1e10/RANGE_LIMITS[2], RANGE_LIMITS[3], RANGE_LIMITS[2], True)

  #print('Ticker-', RANGE_LIMITS[3], RANGE_LIMITS[2], 'price', 1/RANGE_LIMITS[3], 'curr', 1/20300 )
  
  print('Symbol', tr.symbol())
  print('Ticks', tr.upperTick(), tr.lowerTick())
  with brownie.reverts("!InitProxy"): 
    tr.initProxy(oracle, wbtc, usdc, RANGE_LIMITS[0]*1e10, RANGE_LIMITS[1]*1e10, 1/RANGE_LIMITS[0], 1/RANGE_LIMITS[0], True)
  '''
  print('liqR', RANGE_LIMITS[2], RANGE_LIMITS[3], liquidityRatio(1/RANGE_LIMITS[2], 1/RANGE_LIMITS[3]))
  print('liqR', RANGE_LIMITS[0], RANGE_LIMITS[1], liquidityRatio(1/RANGE_LIMITS[0], 1/RANGE_LIMITS[1]))
  print('liqR', liquidityRatio(0.0000001, 1))
  '''
  usdc.approve(tr, 2**256-1, {"from": owner})
  wbtc.approve(tr, 2**256-1, {"from": owner})
  with brownie.reverts(): tr.init(0, 1e6, {"from": owner}) # Uniswap throws: USDC in a WBTC only position
  tr.init(1e6, 0, {"from": owner}) 
  
  with brownie.reverts(): tr.deposit(0, 1e6, {"from": owner}) # Add USDC in WBTC only
  tr.deposit(1e6, 0, {"from": owner})
  
  tr.approve(user, 2**256-1, {"from": owner})
  assert tr.allowance(owner, user) == 2**256-1
  
  with brownie.reverts(): tr.withdraw( 0, 0, 0, {"from": owner})
  with brownie.reverts("ERC20: burn amount exceeds balance"): tr.withdraw( tr.balanceOf(owner)+1, 0, 0, {"from": owner})
  tr.withdraw( tr.balanceOf(owner)/2, 0, 0, {"from": owner})
  tr.withdraw( tr.balanceOf(owner), 0, 0, {"from": owner})


def test_TR(accounts, owner, lendingPool, wbtc, usdc, user, interface, router, routerV3, oracle, TokenisableRange, liquidityRatio):
  usdAmount, btcAmount = liquidityRatio(1/RANGE_LIMITS[3], 1/RANGE_LIMITS[0])
  print('amounts',usdAmount, btcAmount)
  tr = TokenisableRange.deploy({"from": owner})
  print('oracle price', oracle.getAssetPrice(wbtc))
  tr.initProxy(oracle, wbtc, usdc, 1e10/RANGE_LIMITS[3], 1e10/RANGE_LIMITS[0],RANGE_LIMITS[0], RANGE_LIMITS[3], False)
  print('Symbol', tr.symbol())
  print('Ticks', tr.lowerTick(), tr.upperTick())
  
  with brownie.reverts("!InitProxy"): 
    tr.initProxy(oracle, wbtc, usdc, 1e10/RANGE_LIMITS[0], 1e10/RANGE_LIMITS[3],RANGE_LIMITS[0], RANGE_LIMITS[3], True)
        
  usdc.approve(tr, 2**256-1, {"from": owner})  
  wbtc.approve(tr, 2**256-1, {"from": owner})
  with brownie.reverts(): tr.init(0, 1e6, {"from": owner}) # Uniswap throws: unbalanced liquidity added
  tr.init(btcAmount, usdAmount, {"from": owner})
  
  with brownie.reverts(): tr.deposit(0, 1e6, {"from": owner})
  tr.deposit(btcAmount, usdAmount, {"from": owner})
  
  tr.claimFee()  #no fees to claim
  usdc.approve(routerV3, 2**256-1, {"from": owner} )
  wbtc.approve(routerV3, 2**256-1, {"from": owner} )
  routerV3.exactInputSingle([usdc, wbtc, 3000, owner, 2e20, 1e10, 0, 0], {"from": owner})
  routerV3.exactInputSingle([wbtc, usdc, 3000, owner, 2e20, 1e7, 0, 0], {"from": owner})
  
  with brownie.reverts("ERC20: burn amount exceeds balance"): tr.withdraw( tr.balanceOf(owner)+1, 0, 0, {"from": owner})
  tr.withdraw( tr.balanceOf(owner)/2, 0, 0, {"from": owner})



def test_ranger_overlap(owner, RangeManager, lendingPool, usdc, wbtc, router, TokenisableRange, UpgradeableBeacon):
  r = RangeManager.deploy(lendingPool, wbtc, usdc, {"from": owner})
  tr = TokenisableRange.deploy({"from": owner})
  trb = UpgradeableBeacon.deploy(tr, {"from": owner})
  
  with brownie.reverts("Range invalid"): r.generateRange(2000, 1600, 'xxx', 'yyy', trb, {"from": owner})
  r.generateRange(1200, 1600, 'xxx', 'yyy', trb, {"from": owner})
  with brownie.reverts("Range overlap"): r.generateRange(1000, 1400, 'xxx', 'yyy', trb, {"from": owner})
  with brownie.reverts("Range overlap"): r.generateRange(1400, 1800, 'xxx', 'yyy', trb, {"from": owner})
  with brownie.reverts("Range overlap"): r.generateRange(1400, 1500, 'xxx', 'yyy', trb, {"from": owner})
  


@pytest.fixture(scope="module", autouse=True)
def prep_ranger(accounts, owner, timelock, lendingPool, wbtc, usdc, user, interface, router, oracle, config, contracts, TokenisableRange,seed_accounts,liquidityRatio):
  tr, trb, r = contracts

  ranges = [ [1/RANGE_LIMITS[3], 1/RANGE_LIMITS[2]], [1/RANGE_LIMITS[2], 1/RANGE_LIMITS[1]], [1/RANGE_LIMITS[1], 1/RANGE_LIMITS[0]] ]
  for i in ranges:
    r.generateRange( i[0]*1e10, i[1]*1e10, i[0], i[1], trb, {"from": owner})

  # Approve rangeManager for initRange
  wbtc.approve(r, 2**256-1, {"from": owner})
  usdc.approve(r, 2**256-1, {"from": owner})
  
  for i in range(r.getStepListLength()):
    usdAmount, btcAmount = liquidityRatio( ranges[i][0], ranges[i][1])
    r.initRange(r.tokenisedRanges(i), btcAmount, usdAmount, {"from": owner})
    usdAmount, btcAmount = liquidityRatio( (ranges[i][0]+ranges[i][1])/2,(ranges[i][0]+ranges[i][1])/2 *1.001)
    r.initRange(r.tokenisedTicker(i), btcAmount, usdAmount, {"from": owner})  
  
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

  for i in reserves: config.batchInitReserve([i], {"from": timelock})

  # Enable as collateral
  for i in addresses: config.configureReserveAsCollateral(i, 9250, 9500, 10300, {"from":owner, "required_confs":0})


# Check balances and price
def test_ranges_values(owner, lendingPool, wbtc, usdc, user, interface, oracle, contracts, TokenisableRange, prep_ranger):
  tr, trb, r = contracts
  
  # expect added balance in 1st ticker to be the same as balance estimate
  (uBal, eBal) = TokenisableRange.at(r.tokenisedTicker(0)).returnExpectedBalance(0, 0) 
  assert eBal == 0 and round( (10e6 - uBal) / 10e6 ) <= 1 # allow a 1 rounding error
  # above a range, price and balance should remain constant as it contains USDC only
  for i in range(3):
    assert TokenisableRange.at(r.tokenisedTicker(i)).returnExpectedBalance(100000e8, 1e8) == TokenisableRange.at(r.tokenisedTicker(i)).returnExpectedBalance(200000e8, 1e8)
    assert TokenisableRange.at(r.tokenisedTicker(i)).getValuePerLPAtPrice(100000e8, 1e8) == TokenisableRange.at(r.tokenisedTicker(i)).getValuePerLPAtPrice(200000e8, 1e8) 
    assert TokenisableRange.at(r.tokenisedRanges(i)).returnExpectedBalance(100000e8, 1e8) == TokenisableRange.at(r.tokenisedRanges(i)).returnExpectedBalance(200000e8, 1e8)
    assert TokenisableRange.at(r.tokenisedRanges(i)).getValuePerLPAtPrice(100000e8, 1e8) == TokenisableRange.at(r.tokenisedRanges(i)).getValuePerLPAtPrice(200000e8, 1e8) 
  # below a range, balance remains constant
  for i in range(3):
    assert TokenisableRange.at(r.tokenisedRanges(i)).returnExpectedBalance(1000e8, 1e8) == TokenisableRange.at(r.tokenisedRanges(i)).returnExpectedBalance(2000e8, 1e8)
  # above a tick should be usdc only, below should be wbtc only

  assert TokenisableRange.at(r.tokenisedTicker(0)).returnExpectedBalance(30000e8, 1e8)[0] == 0 # above, no wbtc
  assert TokenisableRange.at(r.tokenisedTicker(0)).returnExpectedBalance(300e8, 1e8)[1] == 0 # below, no usdc
  

# Empty an empty range
def test_ranger_3(owner, lendingPool, wbtc, usdc, user, interface, capsys, oracle, contracts, TokenisableRange, prep_ranger):
  tr, trb, r = contracts
  r.removeAssetsFromStep(0, {"from":owner})


# Add/remove amounts from ticker
def test_ranger_4(owner, timelock, lendingPool, wbtc, usdc, user, interface, capsys, oracle, contracts, TokenisableRange, prep_ranger, liquidityRatio):
  tr, trb, r = contracts
  lendingPool.PMAssign(r, {"from": timelock})
  usdAmount, btcAmount = liquidityRatio( 1/RANGE_LIMITS[3], 1/RANGE_LIMITS[2] )
  print(usdAmount, btcAmount)
  
  # Do Ticker transfer call tests
  r.transferAssetsIntoTickerStep(0, btcAmount, 0, {"from":user}) # below tick, only WBTC
  t = interface.IAToken( lendingPool.getReserveData(r.tokenisedTicker(0))[7] )
  assert round(t.balanceOf(user) / 1e9 ) == 1e9 # leave margin for dust rounding error # initial liquidity: $1 = 1e18 LP
  r.removeAssetsFromStep(0, {"from":user})
  assert t.balanceOf(user) == 0
  
  usdAmount, btcAmount = liquidityRatio( 1/RANGE_LIMITS[1], 1/RANGE_LIMITS[0] )
  r.transferAssetsIntoRangerStep(2, 0, usdAmount, {"from":user}) # above range only USDC
  t = interface.IAToken( lendingPool.getReserveData(r.tokenisedRanges(2))[7] )
  assert round(t.balanceOf(user) / 1e9 ) == 1e9
  r.removeAssetsFromStep(2, {"from":user})
  assert t.balanceOf(user) == 0
  
  #r.transferAssetsIntoRangerStep(1, usdAmount, btcAmount, {"from":owner})
  #r.removeAssetsFromAddress(r.tokenisedRanges(1))
  #r.removeAssetsFromStep(1, {"from":owner})


#@pytest.mark.skip_coverage
def test_ranger_5(owner, timelock, lendingPool, wbtc, usdc, user, interface, contracts, TokenisableRange, prep_ranger, liquidityRatio):
  tr, trb, r = contracts
  lendingPool.PMAssign(r, {"from": timelock})
  usdAmount, btcAmount = liquidityRatio(1/RANGE_LIMITS[2], 1/RANGE_LIMITS[1])
  
  # Do Ticker transfer call tests
  #r.transferAssetsIntoTickerStep(1, 566.9e6, 0, {"from":owner}) # current range
  r.transferAssetsIntoRangerStep(1, btcAmount, usdAmount, {"from":owner})
  #r.removeAssetsFromStep(1, {"from":owner})

