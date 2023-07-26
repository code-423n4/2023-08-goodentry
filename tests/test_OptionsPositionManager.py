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
UNISWAPPOOLV3_3 = "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8" # ETH univ3 ETH-USDC 0.3%
# LPAD for btc 0xe7f6F6Cd1Be8313a05e0E38bA97B2A5Dfed7616d - for weth "0x01b76559D512Fa28aCc03630E8954405BcBB1E02"
LENDING_POOL_ADDRESSES_PROVIDER = "0x01b76559D512Fa28aCc03630E8954405BcBB1E02" 
AAVE_WETH = "0x030ba81f1c18d280636f32af80b9aad02cf0854e"
AAVE_USDC = "0xbcca60bb61934080951369a648fb03df4f96263c"
NULL = "0x0000000000000000000000000000000000000000"

# Careful: ticker range now in middle of range, testing ticker
RANGE_LIMITS = [500, 800, 1500, 2500, 5000]

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


# Check if 2 values are within 0.1%
def nearlyEqual(value0, value1):
  if (value1 == 0): return value1 == value0
  else: return abs (value0-value1) / value1 < 0.001



@pytest.fixture(scope="module", autouse=True)
def prep_ranger(accounts, owner, timelock, lendingPool, weth, usdc, user, interface, oracle, config, contracts, TokenisableRange, seed_accounts, liquidityRatio):
  tr, trb, r = contracts

  ranges = [ [RANGE_LIMITS[0], RANGE_LIMITS[1]], [RANGE_LIMITS[1], RANGE_LIMITS[2]], [RANGE_LIMITS[2], RANGE_LIMITS[3]] ]
  for i in ranges:
    r.generateRange( i[0]*1e10, i[1]*1e10, i[0], i[1], trb, {"from": owner})

  # Approve rangeManager for initRange
  weth.approve(r, 2**256-1, {"from": owner})
  usdc.approve(r, 2**256-1, {"from": owner})

  # The following lazily fills all the ticks and ranges except the current active one (e.g. 1600-2000)
  # as there's slippage protection, the active Ranger needs to have the correct ratio 
  # - i usually just use uniswap to figure out the ratio i need to deposit, didn't try to calculate

  for i in range(r.getStepListLength()):
    usdAmount, ethAmount = liquidityRatio( ranges[i][0], ranges[i][1])  
    r.initRange(r.tokenisedRanges(i), usdAmount * 100, 100 * ethAmount, {"from": owner})
    usdAmount, ethAmount = liquidityRatio( (ranges[i][0]+ranges[i][1])/2,(ranges[i][0]+ranges[i][1])/2 + 1)
    r.initRange(r.tokenisedTicker(i), usdAmount * 100, 100 * ethAmount, {"from": owner})  
  
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
  for i in addresses:
    config.configureReserveAsCollateral(i, 9250, 9500, 10300, {"from": timelock})
    config.enableBorrowingOnReserve(i, True, {"from": timelock})

  # deposit in lending pool for borrowing
  for i in addresses:
    tr = TokenisableRange.at(i)
    tr.approve(lendingPool, 2**256-1, {"from": owner})
    lendingPool.deposit(tr, tr.balanceOf(owner), owner, 0, {"from": owner})
  


# Deposit collateral and open position
def test_deploy(accounts, chain, pm, owner, timelock, lendingPool, OptionsPositionManager, roerouter):
  with brownie.reverts("Invalid address"): OptionsPositionManager.deploy( "0x0000000000000000000000000000000000000000", {"from": owner})
  OptionsPositionManager.deploy(roerouter, {"from": owner})
  
  
  
# Deposit collateral and open position
def test_unallowed_flashloan_call(pm, owner, roerouter):
  poolId = roerouter.getPoolsLength() - 1
  from eth_abi import encode_abi

  # levearge direct call unallowed
  calldata = encode_abi(['uint8', 'uint', 'address', 'address'], [0, poolId, NULL, NULL])
  with brownie.reverts("OPM: Call Unallowed"):
    pm.executeOperation([], [], [], owner, calldata, {"from": owner})

  # liquidation direct call unallowed
  calldata = encode_abi(['uint8', 'uint', 'address', 'address'], [1, poolId, NULL, NULL])
  with brownie.reverts("OPM: Call Unallowed"):
    pm.executeOperation([], [], [], owner, calldata, {"from": owner})



def test_swap(accounts, chain, pm, owner, timelock, lendingPool, weth, usdc, user, interface, router, oracle, contracts, TokenisableRange, config, OptionsPositionManager, roerouter):
  lendingPool.PMAssign(pm, {"from": timelock })
  poolId = roerouter.getPoolsLength() - 1
  usdcBalBef = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wethBalBef = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  print('bef swap', usdcBalBef, wethBalBef)
  pm.swapTokens(poolId, usdc, 0, {"from": user})
  usdcBalAft = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wethBalAft = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  print('aft swap', usdcBalAft, wethBalAft)
  
  valBef = oracle.getAssetPrice(usdc) * usdcBalBef / 1e6 + oracle.getAssetPrice(weth) *  wethBalBef / 1e18
  valAft = oracle.getAssetPrice(usdc) * usdcBalAft / 1e6 + oracle.getAssetPrice(weth) *  wethBalAft / 1e18
  valDiff = abs(valAft - valBef)
  assert valDiff / valBef < 0.01 # difference should be less than 1%, including fee and max slippage 1%

  # swap the other way
  usdcBalBef = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wethBalBef = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  print('bef swap', usdcBalBef, wethBalBef)
  pm.swapTokens(poolId, weth, 0, {"from": user})
  usdcBalAft = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wethBalAft = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  valBef = oracle.getAssetPrice(usdc) * usdcBalBef / 1e6 + oracle.getAssetPrice(weth) *  wethBalBef / 1e18
  valAft = oracle.getAssetPrice(usdc) * usdcBalAft / 1e6 + oracle.getAssetPrice(weth) *  wethBalAft / 1e18
  valDiff = abs(valAft - valBef)
  assert valDiff / valBef < 0.01 # difference should be less than 1%, including fee and max slippage 1%

def test_buy_options(accounts, chain, pm, owner, timelock, lendingPool, weth, usdc, user, interface, router, oracle, contracts, TokenisableRange, prep_ranger, config, OptionsPositionManager, roerouter):
  tr, trb, r = contracts
  lendingPool.PMAssign(pm, {"from": timelock })
  poolId = roerouter.getPoolsLength() - 1
  ticker0 = TokenisableRange.at(r.tokenisedTicker(0))
  ticker1 = TokenisableRange.at(r.tokenisedTicker(2))

  print('befd', lendingPool.getUserAccountData(owner))
  lendingPool.borrow(weth, 1e18, 2, 0, owner, {"from": owner})
  print('aftd', lendingPool.getUserAccountData(owner))

  borrowAmount = 1e16

  interface.ICreditDelegationToken( lendingPool.getReserveData(ticker0)[9] ).approveDelegation(pm, 2**256-1, {"from": user})
  interface.ICreditDelegationToken( lendingPool.getReserveData(ticker1)[9] ).approveDelegation(pm, 2**256-1, {"from": user})
  usdc.approve(pm, 2**256-1, {"from": user})
  
  # Should fail if ill-formed inputs
  with brownie.reverts('OPM: Array Length Mismatch'):
    pm.buyOptions(poolId, [ticker0, ticker1], [borrowAmount], ["0x0000000000000000000000000000000000000000", "0x0000000000000000000000000000000000000000"], {"from": user})
  with brownie.reverts('OPM: Array Length Mismatch'): 
    pm.buyOptions(poolId, [ticker0, ticker1], [borrowAmount, borrowAmount], ["0x0000000000000000000000000000000000000000"], {"from": user})
    
  # BUY PUTS: borrow ticker below current price (full USDC)
  ubalbef = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  pm.buyOptions(poolId, [ticker0], [borrowAmount], ["0x0000000000000000000000000000000000000000"], {"from": user})
  # assert that amount borrowed + previous balance = current balance
  assert ubalbef + ticker0.getTokenAmounts(borrowAmount)[0] == interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  print ('debt', lendingPool.getUserAccountData(user)[1], 'expected', ticker0.latestAnswer() * borrowAmount / 1e18 )

  
  # BUY CALLS: borrow ticker  above price (= full ETH)
  wbalbef = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  with brownie.reverts('OPM: Invalid Swap Token'): pm.buyOptions(poolId, [ticker1], [borrowAmount], [TREASURY], {"from": user})
  pm.buyOptions(poolId, [ticker1], [borrowAmount], ["0x0000000000000000000000000000000000000000"], {"from": user})
  # assert that amount borrowed + previous balance = current balance (modulo small rounding errors from USDC or bc debt interst rate means slightly lower underlying tokens)
  assert wbalbef + ticker1.getTokenAmounts(borrowAmount)[1] == interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  
  
  # BUY MULTIPLE OPTIONS: OTM puts and OTM calls
  ubalbef = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wbalbef = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  pm.buyOptions(poolId, [ticker0, ticker1], [borrowAmount, borrowAmount], ["0x0000000000000000000000000000000000000000", "0x0000000000000000000000000000000000000000"], {"from": user})
  # Nearly equal as running interest will increase supply -> slightly decrease underlying tokens withdrawn
  print ('weth', wbalbef + ticker1.getTokenAmounts(borrowAmount)[1], interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user) )
  assert nearlyEqual(wbalbef + ticker1.getTokenAmounts(borrowAmount)[1], interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user) )
  print ('usdc', ubalbef + ticker0.getTokenAmounts(borrowAmount)[0], interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user) )
  assert ubalbef + ticker0.getTokenAmounts(borrowAmount)[0] == interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)


  # BUY ITM CALLS: buy OTM puts, swap to call
  ubalbef = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wbalbef = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  pm.buyOptions(poolId, [ticker0], [borrowAmount], [usdc], {"from": user})
  assert ubalbef == interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user) # USDC bal hasnt changed
  # hard to check exactly the value out for ETH
  print ('wbal bef - aft', wbalbef, interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user) )

  # BUY ITM PUTS: buy OTM calls, swap to puts
  ubalbef = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wbalbef = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  pm.buyOptions(poolId, [ticker1], [borrowAmount], [weth], {"from": user})
  assert nearlyEqual(wbalbef, interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user) )
  print ('ubal bef - aft', ubalbef, interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user) )
  
  # cant close position of another user as health ratio too high
  with brownie.reverts("Not initiated by user"):
    pm.close(poolId, user, ticker0, 0, weth, {"from": owner} )
    

  pm.close(poolId, user, ticker0, interface.ERC20(lendingPool.getReserveData(ticker0)[9]).balanceOf(user), weth, {"from": user} )
  # repay more than the debt will just repay all
  pm.close(poolId, user, ticker1, 1 + interface.ERC20(lendingPool.getReserveData(ticker1)[9]).balanceOf(user), weth, {"from": user} )
  
  print('debt tr0', interface.ERC20(lendingPool.getReserveData(ticker0)[9]).balanceOf(user) )
  assert interface.ERC20(lendingPool.getReserveData(ticker0)[9]).balanceOf(user) == 0
  print('debt tr1', interface.ERC20(lendingPool.getReserveData(ticker1)[9]).balanceOf(user) )
  assert interface.ERC20(lendingPool.getReserveData(ticker1)[9]).balanceOf(user) == 0



def test_sell_fake_option(accounts, chain, pm, owner, timelock, lendingPool, weth, usdc, user, interface, router, oracle, TokenisableRange, OptionsPositionManager, roerouter):
  lendingPool.PMAssign(pm, {"from": timelock })
  poolId = roerouter.getPoolsLength() - 1
  # Create a new ticker that isn't accepted by the lending pool
  tr = TokenisableRange.deploy({"from": owner})

  tr.initProxy(oracle, usdc, weth, RANGE_LIMITS[0]*1e10, RANGE_LIMITS[1]*1e10, RANGE_LIMITS[0], RANGE_LIMITS[1], True)
  usdc.approve(tr, 2**256-1, {"from": owner})
  tr.init(1e6, 0, {"from": owner})
  
  with brownie.reverts("OPM: Invalid Address"): pm.sellOptions(poolId, tr, 1e6, 0, {"from": owner})



def test_sell_option(pm, user, owner, timelock, lendingPool, weth, usdc, interface, oracle, contracts, TokenisableRange, roerouter):
  tr, trb, r = contracts
  lendingPool.PMAssign(pm, {"from": timelock })
  poolId = roerouter.getPoolsLength() - 1
  
  tr = TokenisableRange.at(r.tokenisedTicker(0))
  pm.sellOptions(poolId, tr, 1e6, 0, {"from": user})
  oBal = interface.ERC20( lendingPool.getReserveData(tr)[7] ).balanceOf(user)
  assert nearlyEqual( oracle.getAssetPrice(usdc), oracle.getAssetPrice(tr) *  oBal / 1e18)
  
  prevBal = interface.ERC20( lendingPool.getReserveData(tr)[7] ).balanceOf(owner)
  tr = TokenisableRange.at(r.tokenisedTicker(2))
  pm.sellOptions(poolId, tr, 0, 1e16, {"from": owner})
  oBal = interface.ERC20( lendingPool.getReserveData(tr)[7] ).balanceOf(owner)
  assert nearlyEqual( oracle.getAssetPrice(weth) / 100, oracle.getAssetPrice(tr) *  (oBal - prevBal) / 1e18)

  ethBal = interface.ERC20( lendingPool.getReserveData(weth)[7] ).balanceOf(owner)
  pm.withdrawOptions(poolId, tr, oBal / 2, {"from": owner})
  assert nearlyEqual( oBal / 2, interface.ERC20( lendingPool.getReserveData(tr)[7] ).balanceOf(owner))
  


def test_reduce(accounts, chain, pm, owner, timelock, lendingPool, weth, usdc, user, interface, oracle, contracts, TokenisableRange, prep_ranger, roerouter):
  tr, trb, r = contracts
  lendingPool.PMAssign(pm, {"from": timelock })
  poolId = roerouter.getPoolsLength() - 1
  ticker0 = TokenisableRange.at(r.tokenisedTicker(0))
  ticker1 = TokenisableRange.at(r.tokenisedTicker(2))
  borrowAmount = 1e17
  interface.ICreditDelegationToken( lendingPool.getReserveData(ticker0)[9] ).approveDelegation(pm, 2**256-1, {"from": user})
  interface.ICreditDelegationToken( lendingPool.getReserveData(ticker1)[9] ).approveDelegation(pm, 2**256-1, {"from": user})
  
  ubalbef = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wbalbef = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  print( 'uwbal', ubalbef, wbalbef)
  
  # buy OTM call, swap to ITM put, all in USDC
  pm.buyOptions(poolId, [ticker1], [borrowAmount], [weth], {"from": user})
  # buy PUT, dont sell
  pm.buyOptions(poolId, [ticker0], [borrowAmount], [weth], {"from": user})
  assert interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user) == wbalbef
  
  ubalbef = interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user)
  wbalbef = interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user)
  print( 'uwbal', ubalbef, wbalbef)
  
  print('HF bef', lendingPool.getUserAccountData(user))
  #while lendingPool.getUserAccountData(user)[5]/1e18 > 1.02:
  chain.sleep(93000000000); chain.mine(1)
  #while lendingPool.getUserAccountData(user)[5]/1e18 > 1.02: chain.sleep(500000000); chain.mine(1);
  print('checkHF', lendingPool.getUserAccountData(user)[5]/1e18)

  hf = lendingPool.getUserAccountData(user)[5]
  # Liquidator closes the position - reverts if insufficient collateral to pay the liquidation fee, need to pick a collateral the user actually has
  with brownie.reverts('OPM: Insufficient Collateral'):
    pm.close(poolId, user, ticker1, 0, weth, {"from": owner} )
  with brownie.reverts("OPM: Invalid Collateral Asset"):
    pm.close(poolId, user, ticker1, 0, ROUTER, {"from": owner})
  pm.close(poolId, user, ticker1, borrowAmount / 10, usdc, {"from": owner} )
  assert lendingPool.getUserAccountData(user)[5] > hf # soft liquidation should increase HF
  #print(lendingPool.getUserAccountData(user))

  # temp allow PM to open debt for liquidator (he takes on the debt)
  interface.ICreditDelegationToken( lendingPool.getReserveData(ticker1)[9] ).approveDelegation(pm, 2**256-1, {"from": owner})
  # cant liquidate, HF too high
  with brownie.reverts('42'): pm.liquidate(poolId, user, [ticker1], [borrowAmount / 10], usdc, {"from": owner} )
  
  #while lendingPool.getUserAccountData(user)[5]/1e18 > 1:
  chain.sleep(360000); chain.mine(1);
  print(lendingPool.getUserAccountData(user)[5]/1e18)

  print('user roeUSDC-roWETH', interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(user), interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(user) )
  print('value ', ticker1.latestAnswer() )
  print('debt ', interface.ERC20(lendingPool.getReserveData(ticker1)[9]).balanceOf(user) )
  print('user', user)
  print('liquidator', owner)
  liquidator = accounts[5] # unused account to check amounts
  liquidationAmount = 1e16
  l = pm.liquidate(poolId, user, [ticker1], [liquidationAmount], usdc, {"from": liquidator} )
  print('liquidator balances', interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(liquidator), interface.ERC20(lendingPool.getReserveData(weth)[7]).balanceOf(liquidator) )
  print ("liquidator vs liq. value vs liq.fee.%", interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(liquidator), ticker1.latestAnswer() * liquidationAmount / 1e18, interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(liquidator) * 100 / (ticker1.latestAnswer() * liquidationAmount / 1e18) * 100 )
  # liquidator received liq. fees
  assert interface.ERC20(lendingPool.getReserveData(usdc)[7]).balanceOf(liquidator) > 0 
  
  print('checkHF2', lendingPool.getUserAccountData(user)[5]/1e18)
  # liquidate several assets at once
  liquidationAmount = 1e16
  l = pm.liquidate(poolId, user, [ticker0, ticker1], [liquidationAmount, liquidationAmount], usdc, {"from": liquidator} )



def test_sandwich(accounts, chain, pm, owner, timelock, lendingPool, weth, usdc, user, interface, router, oracle, contracts, TokenisableRange, prep_ranger, config, OptionsPositionManager, roerouter):
  tr, trb, r = contracts
  lendingPool.PMAssign(pm, {"from": timelock })
  poolId = roerouter.getPoolsLength() - 1
  ticker0 = TokenisableRange.at(r.tokenisedTicker(0))
  ticker1 = TokenisableRange.at(r.tokenisedTicker(1))
  ticker2 = TokenisableRange.at(r.tokenisedTicker(2))

  borrowAmount = 1e16

  interface.ICreditDelegationToken( lendingPool.getReserveData(ticker0)[9] ).approveDelegation(pm, 2**256-1, {"from": user})
  interface.ICreditDelegationToken( lendingPool.getReserveData(ticker1)[9] ).approveDelegation(pm, 2**256-1, {"from": user})
  usdc.approve(pm, 2**256-1, {"from": user})

  # dislocate uniswap pool: oracle price wont match 
  lotsUsdc = accounts.at(AAVE_USDC, force=True)
  usdc.approve(router, 2**256-1, {"from": lotsUsdc})
  router.swapExactTokensForTokens(5e12, 0, [usdc.address, weth.address], lotsUsdc, chain.time()+86400, {"from": lotsUsdc}) 

  # BUY ITM CALLS: buy OTM puts, swap to call
  with brownie.reverts("UniswapV2Router: INSUFFICIENT_OUTPUT_AMOUNT"): 
    pm.buyOptions(poolId, [ticker0], [borrowAmount], [usdc], {"from": user})

  # dislocate in the other direction
  lotsWETH = accounts.at(AAVE_WETH, force=True)
  weth.approve(router, 2**256-1, {"from": lotsWETH})
  router.swapExactTokensForTokens(100000e18, 0, [weth.address, usdc.address], lotsWETH, chain.time()+86400, {"from": lotsWETH})

  with brownie.reverts("UniswapV2Router: INSUFFICIENT_OUTPUT_AMOUNT"): 
    pm.buyOptions(poolId, [ticker2], [borrowAmount], [weth], {"from": user})


# Skip for coverage as the uniswap tx will cause a memory runaway leak until ganache-cli OOM crash
@pytest.mark.skip_coverage
def test_sandwich(owner, interface, contracts, lendingPool, usdc, weth, TokenisableRange, prep_ranger, roerouter, liquidityRatio, accounts, routerV3, Test_OptionsPositionManager):
  tr, trb, r = contracts
  poolId = roerouter.getPoolsLength() - 1
  range = TokenisableRange.at(r.tokenisedRanges(1)) # current price at fixed block is 1ETH@1268USDC so price is within 2nd range 1100-1300
  test= Test_OptionsPositionManager.deploy(roerouter, {"from": owner})
  
  # sandwich attack when withdrawing 
  aaveUSDC = accounts.at(AAVE_USDC, force=True)
  aaveWETH = accounts.at(AAVE_WETH, force=True)
  usdc.approve(routerV3, 2**256-1, {"from": aaveUSDC} )
  weth.approve(routerV3, 2**256-1, {"from": aaveWETH} )
  
  # user plans on withdraw
  
  (amount0, amount1) = range.getTokenAmounts(1e18)
  print('bef manipulation', amount0, amount1)
  # dislocate Uni pool with a large USDC swap
  slot0 = interface.IUniswapV3Pool(UNISWAPPOOLV3).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  
  routerV3.exactInputSingle([weth, usdc, 500, aaveWETH, 1803751170519, 50000e18, 0, 0], {"from": aaveWETH})
  slot0 = interface.IUniswapV3Pool(UNISWAPPOOLV3).slot0()
  print('slot0', slot0, slot0[0], 1/((slot0[0]**2)/2**192) * 1e12)
  (amount0, amount1) = range.getTokenAmounts(1e18)
  
  print('aft manipulation 1', amount0, amount1)
  
  with brownie.reverts("OPM: Slippage Error"): test.test_checkExpectedBalances(range, 1e18, amount0, amount1)
  

def test_swapTokensForExactTokens(owner, accounts, Test_OptionsPositionManager, usdc, weth, contracts, TokenisableRange, roerouter, router):
  t = Test_OptionsPositionManager.deploy(roerouter, {"from": owner})

  with brownie.reverts("OPM: Invalid Swap Amounts"): t.test_swapTokensForExactTokens(router, 1e18, 1e6, [usdc, weth], {"from": owner})
  with brownie.reverts("OPM: Insufficient Token Amount"): t.test_swapTokensForExactTokens(router, 1e18, 1e12, [usdc, weth], {"from": owner})
  # swap succeeds
  usdc.transfer(t, 1e7, {"from": owner})
  t.test_swapTokensForExactTokens(router, 1e15, 1e7, [usdc, weth], {"from": owner})
  assert weth.balanceOf(t) == 1e15
  
  
def test_getTargetAmountFromOracle(owner, accounts, Test_OptionsPositionManager, usdc, weth, contracts, TokenisableRange, roerouter, router, NullOracle, oracle):
  t = Test_OptionsPositionManager.deploy(roerouter, {"from": owner})
  nullOracleUsd = NullOracle.deploy(usdc, {"from": owner})
  nullOracleEth = NullOracle.deploy(weth, {"from": owner})

  with brownie.reverts("OPM: Invalid Oracle Price"): t.test_getTargetAmountFromOracle(nullOracleUsd, weth, 1e18, usdc)
  with brownie.reverts("OPM: Invalid Oracle Price"): t.test_getTargetAmountFromOracle(nullOracleEth, weth, 1e18, usdc)
  with brownie.reverts("OPM: Target Amount Too Low"): t.test_getTargetAmountFromOracle(oracle, weth, 1, usdc)
  
  res = t.test_getTargetAmountFromOracle(oracle, weth, 1e18, usdc)
  assert nearlyEqual(res * oracle.getAssetPrice(usdc) / 1e6, oracle.getAssetPrice(weth))
  