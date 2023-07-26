import pytest
from brownie import config, accounts, Contract, chain

@pytest.fixture(scope='session', autouse=True)
def user(accounts):
    yield accounts[0]

@pytest.fixture(scope='session', autouse=True)
def maker(accounts):
    yield accounts[1]

@pytest.fixture(scope='session', autouse=True)
def owner(accounts):
  yield accounts.at("0x7433D4158c702Dc6bF0974E0bB4EEA152cfbDd6A", force=True) 
  
  
@pytest.fixture(scope='session', autouse=True)
def timelock(accounts):
  yield accounts.at("0xA10feBCE203086d7A0f6E9A2FA46268Bec7E199F", force=True) 
  # old owner = deployer = 0x7433D4158c702Dc6bF0974E0bB4EEA152cfbDd6A
  # timelock contract 0xA10feBCE203086d7A0f6E9A2FA46268Bec7E199F
  
@pytest.fixture(scope='session', autouse=True)
def user2(accounts):
  user2 = accounts.add(private_key="0x416b8a7d9290502f5661da81f0cf43893e3d19cb9aea3c426cfb36e8186e9c09")
  yield user2
