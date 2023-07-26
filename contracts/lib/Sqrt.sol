// SPDX-License-Identifier: GPL-3.0
pragma solidity 0.8.19;

/// @title Sqrt function
library Sqrt {
  /// @notice Babylonian method for sqrt
  /// @param x sqrt parameter
  function sqrt(uint x) internal pure returns (uint y) {
      uint z = (x + 1) / 2;
      y = x;
      while (z < y) {
          y = z;
          z = (x / z + z) / 2;
      }
  }
}
