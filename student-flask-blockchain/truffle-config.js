/**
 * Truffle configuration
 * Student Blockchain System
 */

module.exports = {
  contracts_build_directory: "./build/contracts",

  compilers: {
    solc: {
      version: "0.8.19",
      settings: {
        optimizer: {
          enabled: true,
          runs: 200
        }
      }
    }
  },

  networks: {
    development: {
      host: "127.0.0.1",
      port: 7545,
      // Keep network_id in sync with the network id returned by Ganache provider.
      // Current Truffle environment detects Ganache network id = 5777.
      network_id: "5777",


      gas: 6000000,
      gasPrice: 20000000000
    }
  }
};