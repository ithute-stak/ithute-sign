using System.Security.Cryptography;
using IthuteSign.Modern.OfflineIntegration;
using Xunit;

public sealed class OfflineSyncTests
{
    [Fact]
    public async Task VerifiedReceiptDoesNotMarkContractSigned()
    {
        var folder = Path.Combine(Path.GetTempPath(), "ithute-sync-" + Guid.NewGuid().ToString("N"));
        try
        {
            var key = RandomNumberGenerator.GetBytes(32);
            var company = Guid.NewGuid();
            var contract = Guid.NewGuid();
            var coordinator = new OfflineSyncCoordinator(new EncryptedEvidenceStore(folder));
            var evidenceId = await coordinator.StageAsync(company, contract, new byte[] { 1, 2, 3 }, key);
            var transport = new EchoTransport();
            var result = await coordinator.DeliverAsync(evidenceId, company, contract, key, transport);
            Assert.False(result.ContractSigned);
            Assert.Equal(evidenceId, result.EvidenceId);
            Assert.Equal("verified-receipt", result.ServerReceiptId);
        }
        finally { if (Directory.Exists(folder)) Directory.Delete(folder, true); }
    }

    [Fact]
    public async Task MismatchedReceiptIsRejected()
    {
        var folder = Path.Combine(Path.GetTempPath(), "ithute-sync-" + Guid.NewGuid().ToString("N"));
        try
        {
            var key = RandomNumberGenerator.GetBytes(32);
            var company = Guid.NewGuid();
            var contract = Guid.NewGuid();
            var coordinator = new OfflineSyncCoordinator(new EncryptedEvidenceStore(folder));
            var evidenceId = await coordinator.StageAsync(company, contract, new byte[] { 4, 5 }, key);
            await Assert.ThrowsAsync<InvalidDataException>(() =>
                coordinator.DeliverAsync(evidenceId, company, contract, key, new WrongReceiptTransport()));
        }
        finally { if (Directory.Exists(folder)) Directory.Delete(folder, true); }
    }


    [Fact]
    public async Task RetryUsesSameEvidenceIdentityAndDigest()
    {
        var folder = Path.Combine(Path.GetTempPath(), "ithute-sync-" + Guid.NewGuid().ToString("N"));
        try
        {
            var key = RandomNumberGenerator.GetBytes(32);
            var company = Guid.NewGuid();
            var contract = Guid.NewGuid();
            var coordinator = new OfflineSyncCoordinator(new EncryptedEvidenceStore(folder));
            var evidenceId = await coordinator.StageAsync(company, contract, new byte[] { 9, 8, 7 }, key);
            var transport = new RecordingTransport();
            var first = await coordinator.DeliverAsync(evidenceId, company, contract, key, transport);
            var second = await coordinator.DeliverAsync(evidenceId, company, contract, key, transport);
            Assert.Equal(first.EvidenceId, second.EvidenceId);
            Assert.Equal(2, transport.Requests.Count);
            Assert.Equal(transport.Requests[0].EvidenceId, transport.Requests[1].EvidenceId);
            Assert.Equal(transport.Requests[0].Sha256Hex, transport.Requests[1].Sha256Hex);
            Assert.False(first.ContractSigned);
            Assert.False(second.ContractSigned);
        }
        finally { if (Directory.Exists(folder)) Directory.Delete(folder, true); }
    }

    private sealed class RecordingTransport : IVerifiedEvidenceTransport
    {
        public List<EvidenceDelivery> Requests { get; } = new();
        public Task<VerifiedEvidenceReceipt> SubmitAndVerifyAsync(EvidenceDelivery request, CancellationToken ct)
        {
            Requests.Add(request);
            return Task.FromResult(new VerifiedEvidenceReceipt(request.EvidenceId, request.CompanyId,
                request.ContractId, request.Sha256Hex, "verified-receipt"));
        }
    }

    private sealed class EchoTransport : IVerifiedEvidenceTransport
    {
        public Task<VerifiedEvidenceReceipt> SubmitAndVerifyAsync(EvidenceDelivery request, CancellationToken ct) =>
            Task.FromResult(new VerifiedEvidenceReceipt(request.EvidenceId, request.CompanyId,
                request.ContractId, request.Sha256Hex, "verified-receipt"));
    }
    private sealed class WrongReceiptTransport : IVerifiedEvidenceTransport
    {
        public Task<VerifiedEvidenceReceipt> SubmitAndVerifyAsync(EvidenceDelivery request, CancellationToken ct) =>
            Task.FromResult(new VerifiedEvidenceReceipt(request.EvidenceId, Guid.NewGuid(),
                request.ContractId, request.Sha256Hex, "invalid-receipt"));
    }
}
