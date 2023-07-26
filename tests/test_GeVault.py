import pytest, brownie
from brownie import network
import math


# CONSTANTS
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
TREASURY="0x50101017adf9D2d06C395471Bc3D6348589c3b97" # random empty
ROUTER="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
ROUTERV3="0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAPPOOLV3 = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640" # ETH univ3 ETH-USDC 0.05%
# LPAD for btc 0xe7f6F6Cd1Be8313a05e0E38bA97B2A5Dfed7616d - for weth "0x01b76559D512Fa28aCc03630E8954405BcBB1E02"
LENDING_POOL_ADDRESSES_PROVIDER = "0x01b76559D512Fa28aCc03630E8954405BcBB1E02" 
AAVE_WETH = "0x030ba81f1c18d280636f32af80b9aad02cf0854e"
AAVE_USDC = "0xbcca60bb61934080951369a648fb03df4f96263c"
NULL = "0x0000000000000000000000000000000000000000"

TICKS = [1000, 1100, 1200, 1300, 1400, 1500]

@pytest.fixture(scope="module", autouse=True)
def weth(interface, accounts):
  # Claim WETH from MATIC-Aave pool
  aaveWETH = accounts.at("0x28424507fefb6f7f8e9d3860f56504e4e5f5f390", force=True)
  weth = interface.IWETH(WETH, owner=aaveWETH)
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
  
@pytest.fixture(scope="module", autouse=True)
def roerouter(RoeRouter, owner):
  roerouter = RoeRouter.deploy(TREASURY, {"from": owner})
  roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, USDC, WETH, ROUTER, {"from": owner})
  yield roerouter

# No isolation when testing uniswap as it will cause reentrancy reverts
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

@pytest.fixture(scope="module", autouse=True)
def pm(OptionsPositionManager, owner, roerouter):
  pm = OptionsPositionManager.deploy(roerouter, {"from": owner})
  yield pm
  
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
  lendingPool.setSoftLiquidationThreshold(102e16, {"from": poolAdmin})
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
    aaveUSDC = accounts.at(AAVE_USDC, force=True)
    aaveWETH = accounts.at(AAVE_WETH, force=True)
    
    weth.approve(lendingPool, 2**256-1, {"from": aaveWETH})
    weth.transfer(owner, 10e18, {"from": aaveWETH})
    weth.withdraw(1e18, {"from": owner})
    lendingPool.deposit(weth, 30e18, owner, 0, {"from": aaveWETH}) 
    #lendingPool.deposit(weth, 30e18, user, 0, {"from": lotsTokens}) 

    usdc.approve(lendingPool, 2**256-1, {"from": aaveUSDC})
    usdc.transfer(owner, 5e10, {"from": aaveUSDC})
    usdc.transfer(user, 5e10, {"from": aaveUSDC})
    lendingPool.deposit(usdc, 30e10, owner, 0, {"from": aaveUSDC}) 
    lendingPool.deposit(usdc, 1e10, user, 0, {"from": aaveUSDC}) 

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
  
@pytest.fixture(scope="module", autouse=True)
def gevault(accounts, chain, pm, owner, timelock, lendingPool, GeVault, roerouter):
  gevault = GeVault.deploy(TREASURY, roerouter, UNISWAPPOOLV3, 0, "GeVault WETHUSDC", "GEV-ETHUSDC", WETH, False, {"from": owner})
  yield gevault
  

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


# Check if 2 values are within 1%
def nearlyEqual(value0, value1):
  if (value1 == 0): return value1 == value0
  else: return abs (value0-value1) / value1 < 0.01


@pytest.mark.skip_coverage
def exactSwap(routerV3, params, extra): # pragma: no cover
  return routerV3.exactInputSingle(params, extra)



@pytest.fixture(scope="module", autouse=True)
def prep_ranger(accounts, owner, timelock, lendingPool, weth, usdc, user, interface, oracle, config, contracts, TokenisableRange, seed_accounts, liquidityRatio, gevault):
  tr, trb, r = contracts
  addresses = []
  
  for i in TICKS:
    t = TokenisableRange.deploy({"from": owner})
    t.initProxy(oracle, usdc, weth, i * 1e10, i * 1.0001 * 1e10, i, i*1.0001, True, {"from": owner})
    print("Ticker", i, t.name(), t.symbol())
    usdAmount, ethAmount = liquidityRatio(i, i*1.0001) 
    usdc.approve(t, 2**256-1, {"from": owner})
    weth.approve(t, 2**256-1, {"from": owner})
    t.init(usdAmount, ethAmount, {"from": owner})
    addresses.append(t)


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
  for i in addresses:
    config.configureReserveAsCollateral(i, 9250, 9500, 10300, {"from": timelock})
    config.enableBorrowingOnReserve(i, True, {"from": timelock})

  # deposit in lending pool for borrowing
  for i in addresses:
    tr = TokenisableRange.at(i)
    tr.approve(lendingPool, 2**256-1, {"from": owner})
    lendingPool.deposit(tr, tr.balanceOf(owner), owner, 0, {"from": owner})
    gevault.pushTick(i, {"from": owner})
  
  # price of ETH at this fixed block is 1262, which means the active ticks should 1000, 1100, 1200, 1300
  gevault.rebalance({"from": owner})


# Deploy contract
def test_deploy(accounts, chain, pm, owner, timelock, lendingPool, GeVault, roerouter):
  with brownie.reverts("GEV: Invalid Treasury"): 
    GeVault.deploy(NULL, roerouter, UNISWAPPOOLV3, 0, "GeVault WETHUSDC", "GEV-ETHUSDC", WETH, False, {"from": owner})
  
  g = GeVault.deploy(TREASURY, roerouter, UNISWAPPOOLV3, 0, "GeVault WETHUSDC", "GEV-ETHUSDC", WETH, False, {"from": owner})
  assert g.latestAnswer() == 0
  
  
# Deploy contract
def test_push_overlap(accounts, chain, pm, owner, timelock, lendingPool, gevault, roerouter):
  first_tick = gevault.ticks(0)
  with brownie.reverts("GEV: Push Tick Overlap"): gevault.pushTick(first_tick, {"from": owner})
  last_tick = gevault.ticks(gevault.getTickLength()-1)
  with brownie.reverts("GEV: Push Tick Overlap"): gevault.pushTick(last_tick, {"from": owner})
  
  with brownie.reverts("GEV: Shift Tick Overlap"): gevault.shiftTick(first_tick, {"from": owner})
  with brownie.reverts("GEV: Shift Tick Overlap"): gevault.shiftTick(last_tick, {"from": owner})
  

def test_disabled(accounts, chain, pm, usdc, owner, timelock, lendingPool, gevault, roerouter, oracle, TokenisableRange):
  usdc.approve(gevault, 2**256-1, {"from": owner})
  gevault.setEnabled(False, {"from": owner})
  with brownie.reverts("GEV: Pool Disabled"): gevault.deposit(usdc, 1e6, {"from": owner})
  
  gevault.setEnabled(True, {"from": owner})
  gevault.deposit(usdc, 1e6, {"from": owner})
  
  
def test_oracle_check_up(accounts, chain, pm, usdc, weth, owner, timelock, lendingPool, gevault, roerouter, oracle, TokenisableRange, routerV3, interface):
  usdc.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(usdc, 1e6, {"from": owner})
  weth.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(weth, 1e18, {"from": owner})

  assert gevault.poolMatchesOracle() == True
  
  # move price downward by dumping much WETH
  aaveUSDC = accounts.at(AAVE_USDC, force=True)
  aaveWETH = accounts.at(AAVE_WETH, force=True)
  usdc.approve(routerV3, 2**256-1, {"from": aaveUSDC} )
  weth.approve(routerV3, 2**256-1, {"from": aaveWETH} )
  slot0 = interface.IUniswapV3Pool(UNISWAPPOOLV3).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  exactSwap(routerV3, [usdc, weth, 500, aaveUSDC, 1803751170519, 38000000e6, 0, 0], {"from": aaveUSDC})
  slot0 = interface.IUniswapV3Pool(UNISWAPPOOLV3).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  # price is now 1380.95
  assert gevault.poolMatchesOracle() == False
  

@pytest.mark.skip_coverage
def test_oracle_check_down(accounts, chain, pm, usdc, weth, owner, timelock, lendingPool, gevault, roerouter, oracle, TokenisableRange, routerV3, interface):
  usdc.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(usdc, 1e6, {"from": owner})
  weth.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(weth, 1e18, {"from": owner})

  assert gevault.poolMatchesOracle() == True
  
  # move price downward by dumping much WETH
  aaveUSDC = accounts.at(AAVE_USDC, force=True)
  aaveWETH = accounts.at(AAVE_WETH, force=True)
  usdc.approve(routerV3, 2**256-1, {"from": aaveUSDC} )
  weth.approve(routerV3, 2**256-1, {"from": aaveWETH} )
  slot0 = interface.IUniswapV3Pool(UNISWAPPOOLV3).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  exactSwap(routerV3, [weth, usdc, 500, aaveWETH, 1803751170519, 30000e18, 0, 0], {"from": aaveWETH})
  slot0 = interface.IUniswapV3Pool(UNISWAPPOOLV3).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  # price is now 1160
  assert gevault.poolMatchesOracle() == False
  

def test_deposit_withdraw_usdc(accounts, chain, pm, usdc, owner, timelock, lendingPool, gevault, roerouter, oracle, TokenisableRange):
  print ("ETH price", oracle.getAssetPrice(WETH))
  print ("vault value", gevault.getTVL())
  
  # the vault is properly balanced, we add USDC, should add equal balance in both tickers
  usdc.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(usdc, 1e6, {"from": owner})

  
  # first deposit should send 0.1% to treasury 
  assert usdc.balanceOf(TREASURY) == 1e3
  
  print("GEV tvl", gevault.getTVL())
  assert nearlyEqual(gevault.getTVL(), oracle.getAssetPrice(usdc))
  t1 = TokenisableRange.at(gevault.ticks(1))
  t2 = TokenisableRange.at(gevault.ticks(2))
  assert gevault.getTickBalance(1) > 0 and gevault.getTickBalance(2) > 0
  assert nearlyEqual(gevault.getTickBalance(1) * t1.latestAnswer(), gevault.getTickBalance(2) * t2.latestAnswer()) # current index is 1, ticks 1, 2 are USDC, tick 3, 4 are WETH
  
  liquidity = gevault.balanceOf(owner)
  gevault.deposit(usdc, 1e6, {"from": owner})
  assert nearlyEqual(liquidity * 2, gevault.balanceOf(owner))
  # 2nd deposit should send 0.3% to treasury (since imbalanced with too much USDC)
  assert usdc.balanceOf(TREASURY) == 4e3
  
  gevault.withdraw(liquidity / 2, usdc, {"from": owner})
  

def test_deposit_withdraw_weth(accounts, usdc, weth, owner, lendingPool, gevault, oracle, TokenisableRange):
  print ("ETH price", oracle.getAssetPrice(WETH))
  print ("vault value", gevault.getTVL())
  
  # the vault is properly balanced, we add WETH, should add equal balance in both tickers
  weth.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(weth, 1e18, {"from": owner})
  
  # first deposit should send 0.1% to treasury 
  assert weth.balanceOf(TREASURY) == 1e15
  
  print("GEV tvl", gevault.getTVL())
  assert nearlyEqual(gevault.getTVL(), oracle.getAssetPrice(weth))
  t3 = TokenisableRange.at(gevault.ticks(3))
  t4 = TokenisableRange.at(gevault.ticks(4))
  assert gevault.getTickBalance(3) > 0 and gevault.getTickBalance(4) > 0
  assert nearlyEqual(gevault.getTickBalance(3) * t3.latestAnswer(), gevault.getTickBalance(4) * t4.latestAnswer()) # current index is 4, ticks 4, 5 are USDC, tick 6, 7 are WETH
  
  liquidity = gevault.balanceOf(owner)
  gevault.deposit(weth, 1e18, {"from": owner})
  assert nearlyEqual(2 * liquidity, gevault.balanceOf(owner))
  # 2nd deposit should send 0.3% to treasury (since imbalanced with too much WETH)
  assert weth.balanceOf(TREASURY) == 4e15
  
  gevault.withdraw(liquidity / 2, weth, {"from": owner})


@pytest.mark.skip_coverage
def test_deposit_withdraw_eth(accounts, usdc, weth, owner, lendingPool, gevault, oracle, TokenisableRange):
  print ("ETH price", oracle.getAssetPrice(WETH))
  print ("vault value", gevault.getTVL())
  weth.withdraw(1e18, {"from": owner})
  
  with brownie.reverts("GEV: Deposit Zero"): gevault.deposit(weth, 0, {"from": owner})
  with brownie.reverts("GEV: Invalid Weth"): gevault.deposit(usdc, 0, {"from": owner, "value": 1e18})
  
  ethbal = owner.balance()
  gevault.deposit(weth, 0, {"from": owner, "value": 1e18})
  print("GEV tvl", gevault.getTVL())
  assert owner.balance() + 1e18 == ethbal
  assert nearlyEqual(gevault.getTVL(), oracle.getAssetPrice(weth))
  t3 = TokenisableRange.at(gevault.ticks(3))
  t4 = TokenisableRange.at(gevault.ticks(4))
  assert gevault.getTickBalance(3) > 0 and gevault.getTickBalance(4) > 0
  assert nearlyEqual(gevault.getTickBalance(3) * t3.latestAnswer(), gevault.getTickBalance(4) * t4.latestAnswer()) # current index is 4, ticks 4, 5 are USDC, tick 6, 7 are WETH
  
  liquidity = gevault.balanceOf(owner)
  gevault.withdraw(liquidity / 2, weth, {"from": owner})
  assert nearlyEqual( owner.balance() + 5e17 , ethbal)
    
  
def test_max_cap(accounts, weth, owner, lendingPool, gevault, oracle, TokenisableRange):
  newCap = 1e14
  gevault.setTvlCap(newCap)
  assert gevault.tvlCap() == newCap;
  print("0")
  weth.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(weth, 1e18, {"from": owner})
  print("1")
  liquidity = gevault.balanceOf(owner)
  # TVL is now $1262
  print("0#liq", liquidity)
  gevault.setTvlCap(1e11) # sets max tvl to $1k

  with brownie.reverts("GEV: Max Cap Reached"): gevault.deposit(weth, 5e17, {"from": owner})
  with brownie.reverts("GEV: Max Cap Reached"): gevault.deposit(weth, 0, {"from": owner, "value": 5e17})

  # Remove 90% liquidity, should remain ~$120 in the pool
  gevault.withdraw(liquidity / 1.1, weth, {"from": owner})
  print("6")
  # Now adding ~600 should work 
  gevault.deposit(weth, 5e17, {"from": owner})
  

@pytest.mark.skip_coverage
def test_rebalance_down(accounts, interface, weth, usdc, owner, gevault, oracle, routerV3, lendingPool, HardcodedPriceOracle):
  usdc.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(usdc, 1000e6, {"from": owner})
  weth.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(weth, 1e18, {"from": owner})

  # initially the tickIndex is 1
  assert gevault.getActiveTickIndex() == 1
  
  # move price downward by dumping much WETH
  aaveUSDC = accounts.at(AAVE_USDC, force=True)
  aaveWETH = accounts.at(AAVE_WETH, force=True)
  usdc.approve(routerV3, 2**256-1, {"from": aaveUSDC} )
  weth.approve(routerV3, 2**256-1, {"from": aaveWETH} )
  POOL="0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640" # ETH univ3 ETH-USDC 0.05%
  slot0 = interface.IUniswapV3Pool(POOL).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  exactSwap(routerV3, [weth, usdc, 500, aaveWETH, 1803751170519, 30000e18, 0, 0], {"from": aaveWETH})
  slot0 = interface.IUniswapV3Pool(POOL).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  # price is now 1160
  
  # after rebalancing, tick 3 should have assets while tick 7 should have nothing
  for k in range(gevault.getTickLength()):
    tkp = lendingPool.getReserveData(gevault.ticks(k))[7]
    print('bal', k, interface.ERC20(tkp).balanceOf(gevault))

  # we moved 1 tick down so new lower tick should be 0
  assert gevault.getActiveTickIndex() == 0
  
  # failure bc price moved, possible sandwich attack
  with brownie.reverts("GEV: Oracle Error"): gevault.rebalance({"from": owner})
  
  # deploy fixed price oracle
  print("old oracle price", oracle.getAssetPrice(weth))
  neworacle = HardcodedPriceOracle.deploy(116000000000, {"from": owner})
  lpadd = interface.ILendingPoolAddressesProvider(LENDING_POOL_ADDRESSES_PROVIDER)
  poolAdmin = accounts.at(lpadd.getPoolAdmin(), force=True)
  oracle.setAssetSources([WETH], [neworacle], {"from": poolAdmin})
  print("new oracle price", oracle.getAssetPrice(weth))
  gevault.rebalance({"from": owner})

  for k in range(gevault.getTickLength()):
    tkp = lendingPool.getReserveData(gevault.ticks(k))[7]
    print('bal', k, interface.ERC20(tkp).balanceOf(gevault))
  

@pytest.mark.skip_coverage
def test_rebalance_up(accounts, interface, weth, usdc, owner, gevault, oracle, routerV3, lendingPool, HardcodedPriceOracle):
  usdc.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(usdc, 1000e6, {"from": owner})
  weth.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(weth, 1e18, {"from": owner})

  # initially the tickIndex is 1
  assert gevault.getActiveTickIndex() == 1
  
  # move price upward by buying much WETH
  aaveUSDC = accounts.at(AAVE_USDC, force=True)
  aaveWETH = accounts.at(AAVE_WETH, force=True)
  usdc.approve(routerV3, 2**256-1, {"from": aaveUSDC} )
  weth.approve(routerV3, 2**256-1, {"from": aaveWETH} )
  POOL="0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640" # ETH univ3 ETH-USDC 0.05%
  slot0 = interface.IUniswapV3Pool(POOL).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  exactSwap(routerV3, [usdc, weth, 500, aaveUSDC, 1803751170519, 38000000e6, 0, 0], {"from": aaveUSDC})
  slot0 = interface.IUniswapV3Pool(POOL).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  # price is now 1380.95
  
  for k in range(gevault.getTickLength()):
    tkp = lendingPool.getReserveData(gevault.ticks(k))[7]
    print('bal', k, interface.ERC20(tkp).balanceOf(gevault))

  # we moved 1 tick up so new lower tick should be 2
  assert gevault.getActiveTickIndex() == 2

  # failure bc price moved, possible sandwich attack
  with brownie.reverts("GEV: Oracle Error"): gevault.rebalance({"from": owner})
  
  # deploy fixed price oracle
  print("old oracle price", oracle.getAssetPrice(weth))
  neworacle = HardcodedPriceOracle.deploy(138000000000, {"from": owner})
  lpadd = interface.ILendingPoolAddressesProvider(LENDING_POOL_ADDRESSES_PROVIDER)
  poolAdmin = accounts.at(lpadd.getPoolAdmin(), force=True)
  oracle.setAssetSources([WETH], [neworacle], {"from": poolAdmin})
  print("new oracle price", oracle.getAssetPrice(weth))
  gevault.rebalance({"from": owner})

  # after rebalancing, tick 5 should have assets while tick 1 should have nothing
  for k in range(gevault.getTickLength()):
    tkp = lendingPool.getReserveData(gevault.ticks(k))[7]
    print('bal', k, interface.ERC20(tkp).balanceOf(gevault))
  

@pytest.mark.skip_coverage
# Trying to rebalance upward, but the lower ticker has some outstanding debt, so not all can be moved
def test_rebalance_with_debt(accounts, interface, weth, usdc, owner, user, gevault, oracle, routerV3, lendingPool, HardcodedPriceOracle, TokenisableRange):
  usdc.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(usdc, 1262e6, {"from": owner})
  weth.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(weth, 1e18, {"from": owner})

  # initially the tickIndex is 1
  assert gevault.getActiveTickIndex() == 1
  
  # user borrows some of the 1st tick
  t1 = gevault.ticks(1)
  lendingPool.borrow(t1, 100e18, 2, 0, user, {"from": user})

  # move price upward by buying much WETH
  aaveUSDC = accounts.at(AAVE_USDC, force=True)
  aaveWETH = accounts.at(AAVE_WETH, force=True)
  usdc.approve(routerV3, 2**256-1, {"from": aaveUSDC} )
  weth.approve(routerV3, 2**256-1, {"from": aaveWETH} )
  POOL="0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640" # ETH univ3 ETH-USDC 0.05%
  slot0 = interface.IUniswapV3Pool(POOL).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  exactSwap(routerV3, [usdc, weth, 500, aaveUSDC, 1803751170519, 38000000e6, 0, 0], {"from": aaveUSDC})
  slot0 = interface.IUniswapV3Pool(POOL).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  # price is now 1380.95
  
  
  for k in range(gevault.getTickLength()):
    print('bal', k, gevault.getTickBalance(k))

  # we moved 1 tick up so new lower tick should be 2
  assert gevault.getActiveTickIndex() == 2

  # failure bc price moved, possible sandwich attack
  with brownie.reverts("GEV: Oracle Error"): gevault.rebalance({"from": owner})
  
  # deploy fixed price oracle
  print("old oracle price", oracle.getAssetPrice(weth))
  neworacle = HardcodedPriceOracle.deploy(138000000000, {"from": owner})
  #0xBcca60bB61934080951369a648Fb03DF4F96263C

  lpadd = interface.ILendingPoolAddressesProvider(LENDING_POOL_ADDRESSES_PROVIDER)
  poolAdmin = accounts.at(lpadd.getPoolAdmin(), force=True)
  oracle.setAssetSources([WETH], [neworacle], {"from": poolAdmin})
  print("new oracle price", oracle.getAssetPrice(weth))
  gevault.rebalance({"from": owner})

  for k in range(gevault.getTickLength()):
    print('bal', k, gevault.getTickBalance(k))
    
  # assert that all remaining available supply has been moved away when rebalancing
  assert interface.ERC20(lendingPool.getReserveData(t1)[7]).balanceOf(lendingPool) == 0
  
  
def test_fees(accounts, weth, usdc, owner, lendingPool, gevault, oracle, TokenisableRange):
  # getAdjustedBaseFee(increaseToken0): increaseToken0 is True if depositing token0 (here: usdc) or withdrawing token1
  baseFee = gevault.baseFeeX4()
  # vault is empty, so increasing token1 should get half fees
  assert gevault.getAdjustedBaseFee(False) == baseFee / 2
  print("base fee vs adjusted", baseFee, gevault.getAdjustedBaseFee(False) )
  
  # Deposit WETH
  weth.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(weth, 1e18, {"from": owner})
  # pool now is imbalanced with only WETH, so fee for depositing USDC should be halved, fee for WETH should be maxxed out (to +50%)
  assert gevault.getAdjustedBaseFee(False) == baseFee * 1.5
  assert gevault.getAdjustedBaseFee(True) == baseFee / 2
  
  # Deposit USDC, 20% more than ETH in value
  usdc.approve(gevault, 2**256-1, {"from": owner})
  gevault.deposit(usdc, 1262e6 * 1.2, {"from": owner})
  # Pool is imbalanced, with valueUSDC = 1.2 * valueWETH, fee for depositing more USDC should be around 1.2 * baseFee,  -0/-1 for rounding
  print("fees", gevault.getAdjustedBaseFee(True), baseFee, baseFee * 1.2, baseFee * 1.2 - 1)
  assert gevault.getAdjustedBaseFee(True) == baseFee * 1.2 or gevault.getAdjustedBaseFee(True) == baseFee * 1.2 - 1
  print("fees", gevault.getAdjustedBaseFee(False), baseFee, baseFee / 1.2)
  assert gevault.getAdjustedBaseFee(False) == baseFee / 1.2

