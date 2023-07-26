pragma solidity >=0.5.0;

interface IWETH {
  function deposit() external payable;
  function balanceOf(address) external view returns (uint);
  function transfer(address to, uint value) external returns (bool);
  function withdraw(uint) external;
  function allowance(address owner, address spender) external view returns (uint256);
  function approve(address spender, uint256 amount) external returns (bool);
  function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}