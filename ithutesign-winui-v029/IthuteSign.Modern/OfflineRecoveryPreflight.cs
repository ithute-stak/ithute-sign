using System.Security.Cryptography;
using IthuteSign.Modern.OfflineIntegration;

namespace IthuteSign.Modern;

/// <summary>
/// Read-only recovery preflight for the WinUI application. Does not transmit
/// evidence, mark contracts signed, or alter the outbox.
/// The caller must supply a verified, protected workstation key.
/// </summary>
public static class OfflineRecoveryPreflight
{
    public static async Task<OfflineRecoveryStatus> InspectAsync(
        string evidenceDirectory,
        string outboxDirectory,
        byte[] workstationKey,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(evidenceDirectory) ||
            string.IsNullOrWhiteSpace(outboxDirectory))
            throw new ArgumentException("Evidence and outbox directories are required.");
        if (workstationKey is null || workstationKey.Length != 32)
            throw new ArgumentException("Protected 256-bit workstation key is required.");

        // Never generate a replacement key when an existing queue is unreadable.
        var store = new EncryptedEvidenceStore(evidenceDirectory);
        var outbox = new PersistentOutbox(outboxDirectory, new OfflineSyncCoordinator(store));
        var result = await new VerifiedRecoveryAudit(outbox, store)
            .InspectPendingAsync(workstationKey, cancellationToken);

        return new OfflineRecoveryStatus(
            result.VerifiedPendingEvidence.Count,
            result.MissingPendingEvidence.Count,
            result.CorruptPendingEvidence.Count,
            result.SafeToAttemptDelivery);
    }
}

public sealed record OfflineRecoveryStatus(
    int VerifiedPending, int MissingEvidence, int CorruptEvidence,
    bool SafeToAttemptDelivery)
{
    // Read-only preflight is not proof of authentication or server authorization.
    public bool ContractSigned => false;
}
