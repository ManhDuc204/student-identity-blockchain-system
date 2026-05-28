const StudentIdentity = artifacts.require("StudentIdentity");

module.exports = function (deployer) {
  deployer.deploy(StudentIdentity);
};

