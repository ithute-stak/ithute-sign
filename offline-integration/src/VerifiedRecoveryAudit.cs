using System.Security.Cryptography;

namespace IthuteSign.Modern.OfflineIntegration;

/// <summary>
/// Cryptographically verifies each pending outbox record and its matching
/// encrypted evidence. Read-only: does not upload, requeue or delete anything.
/// </summary>
public sealed class VerifiedRecoveryAudit
{
    private readonly PersistentOutbox _outbox;
    private readonly EncryptedEvidenceStore _store;

    public VerifiedRecoveryAudit(PersistentOutbox outbox, EncryptedEvidenceStore store)
    {
        _outbox = outbox ?? throw new ArgumentNullException(nameof(outbox));
        _store = store ?? throw new ArgumentNullException(nameof(store));
    }

    public async Task<VerifiedRecoveryResult> InspectPendingAsync(byte[] workstationKey,
        CancellationToken cancellationToken = default)
    {
        if (workstationKey is null || workstationKey.Length != 32)
            throw new ArgumentException("AES-256 workstation key required.", nameof(workstationKey));
        var pending = await _outbox.PendingAsync(workstationKey, cancellationToken);
        var verified = new List<Guid>();
        var missing = new List<Guid>();
        var corrupt = new List<Guid>();
        foreach (var item in pending)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                var evidence = await _store.ReadAsync(item.EvidenceId, item.CompanyId,
                    item.ContractId, workstationKey, cancellationToken);
                try { verified.Add(item.EvidenceId); }
                finally { CryptographicOperations.ZeroMemory(evidence); }
            }
            catch (FileNotFoundException) { missing.Add(item.EvidenceId); }
            catch (DirectoryNotFoundException) { missing.Add(item.EvidenceId); }
            catch (CryptographicException) { corrupt.Add(item.EvidenceId); }
            catch (InvalidDataException) { corrupt.Add(item.EvidenceId); }
        }
        return new VerifiedRecoveryResult(verified, missing, corrupt);
    }
}

public sealed record VerifiedRecoveryResult(
    IReadOnlyList<Guid> VerifiedPendingEvidence,
    IReadOnlyList<Guid> MissingPendingEvidence,
    IReadOnlyList<Guid> CorruptPendingEvidence)
{
    public bool SafeToAttemptDelivery => MissingPendingEvidence.Count == 0 &&
        CorruptPendingEvidence.Count == 0;
}
