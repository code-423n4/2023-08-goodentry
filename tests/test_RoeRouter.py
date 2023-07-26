import pytest, brownie


# CONSTANTS
NULL = "0x0000000000000000000000000000000000000000"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
WETHUSDC = "0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc"
AMMROUTER="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
LENDING_POOL_ADDRESSES_PROVIDER = "0x01b76559D512Fa28aCc03630E8954405BcBB1E02"


@pytest.fixture(scope="module", autouse=True)
def roerouter(RoeRouter, owner):
  roerouter = RoeRouter.deploy(owner, {"from": owner})
  yield roerouter




# No isolation when testing uniswap as it will cause reentrancy reverts
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_add_pool(accounts, user, owner, roerouter):
  assert roerouter.getPoolsLength() == 0

  with brownie.reverts("Ownable: caller is not the owner"):
    roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, USDC, WETH, AMMROUTER, {"from": user})
    
  with brownie.reverts("Invalid Address"):
    roerouter.addPool(NULL, USDC, WETH, AMMROUTER, {"from": owner})
  with brownie.reverts("Invalid Address"):
    roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, NULL, WETH, AMMROUTER, {"from": owner})
  with brownie.reverts("Invalid Address"):
    roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, USDC, NULL, AMMROUTER, {"from": owner})
  with brownie.reverts("Invalid Address"):
    roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, USDC, WETH, NULL, {"from": owner})
    
  with brownie.reverts("Invalid Order"):
    roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, WETH, USDC, AMMROUTER, {"from": owner})
    
  roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, USDC, WETH, AMMROUTER, {"from": owner})
  
  poollength = roerouter.getPoolsLength()
  assert poollength == 1
  
  pool = roerouter.pools(poollength - 1)
  
  assert pool[0] == LENDING_POOL_ADDRESSES_PROVIDER
  assert pool[1] == USDC
  assert pool[2] == WETH
  assert pool[3] == AMMROUTER
  assert pool[4] == False
  
def test_deprecate_pool(accounts, user, owner, roerouter):
  roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, USDC, WETH, AMMROUTER, {"from": owner})
  poollength = roerouter.getPoolsLength()

  roerouter.deprecatePool(poollength - 1)
  assert roerouter.pools(poollength - 1)[4] == True


def test_update_treasury(accounts, user, owner, roerouter):
  assert roerouter.treasury() == owner.address
  
  with brownie.reverts("Ownable: caller is not the owner"):
    roerouter.setTreasury(user, {"from": user})
  
  roerouter.setTreasury(user, {"from": owner})
  assert roerouter.treasury() == user.address
    