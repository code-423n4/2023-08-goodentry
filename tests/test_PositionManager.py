import pytest, brownie

NULL = "0x0000000000000000000000000000000000000000"
TREASURY="0x50101017adf9D2d06C395471Bc3D6348589c3b97" # random empty
LENDING_POOL_ADDRESSES_PROVIDER = "0x01b76559D512Fa28aCc03630E8954405BcBB1E02"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
ROUTER="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"


@pytest.fixture(scope="module", autouse=True)
def roerouter(RoeRouter, owner):
  roerouter = RoeRouter.deploy(TREASURY, {"from": owner})
  roerouter.addPool(LENDING_POOL_ADDRESSES_PROVIDER, USDC, WETH, ROUTER, {"from": owner})
  yield roerouter


def test_deployment(owner, roerouter, PositionManager):
  with brownie.reverts("Invalid address"):
    pm = PositionManager.deploy(NULL, {"from": owner})
  
  pm = PositionManager.deploy(roerouter, {"from": owner})
  

