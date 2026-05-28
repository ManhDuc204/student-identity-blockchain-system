// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title StudentIdentity
 * @notice Lưu hash danh tính sinh viên lên blockchain để đảm bảo bất biến dữ liệu.
 */
contract StudentIdentity {
    // Mapping: studentId => hash SHA256 (dạng bytes32)
    mapping(string => bytes32) private studentHashes;

    // Tổng số sinh viên đã được thêm
    uint256 public studentsCount;

    // Sự kiện phát ra khi thêm sinh viên
    event StudentAdded(
        string indexed studentId,
        bytes32 indexed dataHash,
        address indexed addedBy,
        uint256 blockNumber
    );

    // Sự kiện phát ra khi "xóa" (chỉ log, không xóa dữ liệu on-chain)
    event StudentDeleted(
        string indexed studentId,
        address indexed deletedBy,
        uint256 timestamp
    );

    /**
     * @notice Thêm mới (hoặc ghi lần đầu) hash cho studentId.
     * @dev Immutable: chỉ cho phép ghi nếu studentId chưa có hash.
     */
    function addStudent(string calldata studentId, bytes32 dataHash) external {
        require(bytes(studentId).length > 0, "studentId required");
        require(dataHash != bytes32(0), "dataHash required");
        require(studentHashes[studentId] == bytes32(0), "studentId already exists");

        studentHashes[studentId] = dataHash;
        studentsCount += 1;

        emit StudentAdded(studentId, dataHash, msg.sender, block.number);
    }

    /**
     * @notice Kiểm tra danh tính sinh viên dựa trên hash.
     * @dev Không thay đổi dữ liệu on-chain.
     */
    function verifyStudent(string calldata studentId, bytes32 dataHash)
        external
        view
        returns (bool)
    {
        require(bytes(studentId).length > 0, "studentId required");
        return studentHashes[studentId] == dataHash;
    }

    /**
     * @notice Lấy hash đã lưu cho studentId.
     */
    function getStudentHash(string calldata studentId) external view returns (bytes32) {
        return studentHashes[studentId];
    }

    /**
     * @notice Ghi log "DELETED" lên blockchain.
     * @dev Không xóa mapping hash để đảm bảo dữ liệu immutable.
     */
    function logDeletion(string calldata studentId) external {
        require(bytes(studentId).length > 0, "studentId required");
        emit StudentDeleted(studentId, msg.sender, block.timestamp);
    }
}


