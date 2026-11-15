using System.Security.Cryptography;
using System.Text.Json;

namespace IthuteSign.Modern.OfflineIntegration;

/// <summary>
/// Offline evidence delivery coordinator. This is a transport-independent
/// prototype: it never invents LoanHub routes or considers upload = signed.
/// The caller supplies a verified server adapter with durable idempotency.
/// </summary>
public sealed class OfflineSyncCoordinator
{
    private readonly EncryptedEvidenceStore _store;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = false };

    public OfflineSyncCoordinator(EncryptedEvidenceStore store) =>
        _store = store ?? throw new ArgumentNullException(nameof(store));

    public async Task<Guid> StageAsync(Guid companyId, Guid contractId,
        byte[] evidence, ReadOnlyMemory<byte> workstationKey,
        CancellationToken cancellationToken = default)
    {
        if (evidence is null) throw new ArgumentNullException(nameof(evidence));
        var evidenceId = Guid.NewGuid();
        // Evidence is encrypted at rest before any delivery is attempted.
        await _store.SaveAsync(evidenceId, companyId, contractId, evidence,
            workstationKey, cancellationToken);
        return evidenceId;
    }

    public async Task<DeliveryResult> DeliverAsync(
        Guid evidenceId, Guid companyId, Guid contractId,
        ReadOnlyMemory<byte> workstationKey, IVerifiedEvidenceTransport transport,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(transport);
        // Prevent concurrent duplicate attempts inside this process. A production
        // implementation also needs an interprocess lock and server idempotency.
        await _gate.WaitAsync(cancellationToken);
        try
        {
            var evidence = await _store.ReadAsync(evidenceId, companyId, contractId,
                workstationKey, cancellationToken);
            try
            {
                var digest = Convert.ToHexString(SHA256.HashData(evidence));
                // Stable idempotency key across retries. This is not an auth token.
                var request = new EvidenceDelivery(
                    evidenceId, companyId, contractId, digest, evidence);
                var result = await transport.SubmitAndVerifyAsync(request, cancellationToken);
                if (result is null || result.EvidenceId != evidenceId ||
                    result.CompanyId != companyId || result.ContractId != contractId ||
                    !string.Equals(result.Sha256Hex, digest, StringComparison.Ordinal) ||
                    string.IsNullOrWhiteSpace(result.ServerReceiptId))
                    throw new InvalidDataException("Remote evidence receipt does not match the submitted evidence.");
                // Receipt only proves evidence acceptance, NOT signed finalization.
                return new DeliveryResult(evidenceId, result.ServerReceiptId, false);
            }
            finally { CryptographicOperations.ZeroMemory(evidence); }
        }
        finally { _gate.Release(); }
    }
}

public sealed record EvidenceDelivery(Guid EvidenceId, Guid CompanyId,
    Guid ContractId, string Sha256Hex, byte[] EvidenceBytes);

public sealed record VerifiedEvidenceReceipt(Guid EvidenceId, Guid CompanyId,
    Guid ContractId, string Sha256Hex, string ServerReceiptId);

public sealed record DeliveryResult(Guid EvidenceId, string ServerReceiptId,
    bool ContractSigned);

/// <summary>
/// Must use real, authenticated LoanHub server endpoints and perform a
/// read-after-write verification or equivalent authoritative receipt check.
/// On network ambiguity, retry with the same EvidenceId and SHA-256 digest.
/// </summary>
public interface IVerifiedEvidenceTransport
{
    Task<VerifiedEvidenceReceipt> SubmitAndVerifyAsync(
        EvidenceDelivery request, CancellationToken cancellationToken);
}
