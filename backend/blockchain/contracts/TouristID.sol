// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title TouristID
/// @notice On-chain registry for time-bound tourist identities.
/// @dev No PII stored on-chain, only a hash of the off-chain record and the
///      trip window. The point of putting this on a chain instead of just
///      trusting one state's database is cross-border verification: any
///      state's checkpoint system can call isValid() directly against the
///      same contract and get the same answer, without needing an API key
///      or a live connection to whichever state originally issued the ID.
///      Issuance stays centralized (only the backend's wallet can issue or
///      revoke) since that matches how this would actually be run - a
///      state tourism department or NIC-operated system, not an open
///      permissionless registry. Verification is public and free to call.
contract TouristID {
    struct Identity {
        address issuer;
        uint256 tripStart;   // unix timestamp
        uint256 tripEnd;     // unix timestamp
        bytes32 dataHash;    // keccak256 of the off-chain tourist record, ties on-chain ID to off-chain data without exposing it
        bool revoked;
    }

    address public owner;
    mapping(bytes32 => Identity) private identities; // key: keccak256(touristId UUID)

    event IdentityIssued(bytes32 indexed touristId, uint256 tripStart, uint256 tripEnd);
    event IdentityRevoked(bytes32 indexed touristId);

    modifier onlyOwner() {
        require(msg.sender == owner, "TouristID: caller is not the issuer");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Issue a new identity. Only callable by the backend's wallet.
    function issueIdentity(
        bytes32 touristId,
        uint256 tripStart,
        uint256 tripEnd,
        bytes32 dataHash
    ) external onlyOwner {
        require(tripEnd > tripStart, "TouristID: tripEnd must be after tripStart");
        require(identities[touristId].tripStart == 0, "TouristID: already issued");

        identities[touristId] = Identity({
            issuer: msg.sender,
            tripStart: tripStart,
            tripEnd: tripEnd,
            dataHash: dataHash,
            revoked: false
        });

        emit IdentityIssued(touristId, tripStart, tripEnd);
    }

    /// @notice Revoke an identity early (lost passport, fraud report, trip cancelled, etc.)
    function revokeIdentity(bytes32 touristId) external onlyOwner {
        require(identities[touristId].tripStart != 0, "TouristID: not found");
        identities[touristId].revoked = true;
        emit IdentityRevoked(touristId);
    }

    /// @notice Anyone can call this - a checkpoint in a different state doesn't
    /// need permission from whoever issued the ID, just the contract address.
    function isValid(bytes32 touristId) external view returns (bool) {
        Identity memory id = identities[touristId];
        if (id.tripStart == 0) return false; // never issued
        if (id.revoked) return false;
        return block.timestamp >= id.tripStart && block.timestamp <= id.tripEnd;
    }

    function getIdentity(bytes32 touristId)
        external
        view
        returns (address issuer, uint256 tripStart, uint256 tripEnd, bytes32 dataHash, bool revoked)
    {
        Identity memory id = identities[touristId];
        return (id.issuer, id.tripStart, id.tripEnd, id.dataHash, id.revoked);
    }
}
