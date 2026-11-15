using System.Security.Cryptography;
using IthuteSign.Modern.OfflineIntegration;
using Xunit;

public sealed class PersistentOutboxTests
{
    [Fact]
    public async Task SurvivesRestartAndRequiresVerifiedReceipt()
    {
        var dir = Path.Combine(Path.GetTempPath(), "ithute-outbox-" + Guid.NewGuid().ToString("N"));
        try
        {
            var key = RandomNumberGenerator.GetBytes(32);
            var sync = new OfflineSyncCoordinator(new EncryptedEvidenceStore(Path.Combine(dir, "evidence")));
            var first = new PersistentOutbox(Path.Combine(dir, "queue"), sync);
            var staged = await first.EnqueueAsync(Guid.NewGuid(), Guid.NewGuid(), new byte[] { 1, 2, 3 }, key);
            var restarted = new PersistentOutbox(Path.Combine(dir, "queue"), sync);
            Assert.Single(await restarted.PendingAsync(key));
            var result = await restarted.DrainAsync(key, new GoodTransport());
            Assert.Equal(1, result.Delivered);
            Assert.Empty(await restarted.PendingAsync(key));
            Assert.True(File.Exists(Path.Combine(dir, "evidence", staged.EvidenceId.ToString("N") + ".evidence")));
        }
        finally { if (Directory.Exists(dir)) Directory.Delete(dir, true); }
    }

    [Fact]
    public async Task InvalidReceiptFailsClosedAndKeepsPending()
    {
        var dir = Path.Combine(Path.GetTempPath(), "ithute-outbox-" + Guid.NewGuid().ToString("N"));
        try
        {
            var key = RandomNumberGenerator.GetBytes(32);
            var sync = new OfflineSyncCoordinator(new EncryptedEvidenceStore(Path.Combine(dir, "evidence")));
            var outbox = new PersistentOutbox(Path.Combine(dir, "queue"), sync);
            await outbox.EnqueueAsync(Guid.NewGuid(), Guid.NewGuid(), new byte[] { 4, 5 }, key);
            await Assert.ThrowsAsync<InvalidDataException>(() => outbox.DrainAsync(key, new BadTransport()));
            Assert.Single(await outbox.PendingAsync(key));
        }
        finally { if (Directory.Exists(dir)) Directory.Delete(dir, true); }
    }

    [Fact]
    public async Task WrongKeyCannotReadQueue()
    {
        var dir = Path.Combine(Path.GetTempPath(), "ithute-outbox-" + Guid.NewGuid().ToString("N"));
        try
        {
            var key = RandomNumberGenerator.GetBytes(32);
            var sync = new OfflineSyncCoordinator(new EncryptedEvidenceStore(Path.Combine(dir, "evidence")));
            var outbox = new PersistentOutbox(Path.Combine(dir, "queue"), sync);
            await outbox.EnqueueAsync(Guid.NewGuid(), Guid.NewGuid(), new byte[] { 6 }, key);
            await Assert.ThrowsAsync<AuthenticationTagMismatchException>(() =>
                outbox.PendingAsync(RandomNumberGenerator.GetBytes(32)));
        }
        finally { if (Directory.Exists(dir)) Directory.Delete(dir, true); }
    }

    private sealed class GoodTransport : IVerifiedEvidenceTransport
    {
        public Task<VerifiedEvidenceReceipt> SubmitAndVerifyAsync(EvidenceDelivery request, CancellationToken ct) =>
            Task.FromResult(new VerifiedEvidenceReceipt(request.EvidenceId, request.CompanyId,
                request.ContractId, request.Sha256Hex, "server-receipt"));
    }

    private sealed class BadTransport : IVerifiedEvidenceTransport
    {
        public Task<VerifiedEvidenceReceipt> SubmitAndVerifyAsync(EvidenceDelivery request, CancellationToken ct) =>
            Task.FromResult(new VerifiedEvidenceReceipt(request.EvidenceId, Guid.NewGuid(),
                request.ContractId, request.Sha256Hex, "wrong-company"));
    }
}
