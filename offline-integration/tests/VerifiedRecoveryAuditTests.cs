using System.Security.Cryptography;
using IthuteSign.Modern.OfflineIntegration;
using Xunit;

public sealed class VerifiedRecoveryAuditTests
{
    [Fact]
    public async Task DetectsTamperedEvidenceBeforeDelivery()
    {
        var root = Path.Combine(Path.GetTempPath(), "ithute-verified-audit-" + Guid.NewGuid().ToString("N"));
        try
        {
            var key = RandomNumberGenerator.GetBytes(32);
            var evidenceRoot = Path.Combine(root, "evidence");
            var store = new EncryptedEvidenceStore(evidenceRoot);
            var outbox = new PersistentOutbox(Path.Combine(root, "queue"),
                new OfflineSyncCoordinator(store));
            var item = await outbox.EnqueueAsync(Guid.NewGuid(), Guid.NewGuid(),
                new byte[] { 1, 2, 3, 4 }, key);
            var auditor = new VerifiedRecoveryAudit(outbox, store);
            var first = await auditor.InspectPendingAsync(key);
            Assert.True(first.SafeToAttemptDelivery);
            Assert.Contains(item.EvidenceId, first.VerifiedPendingEvidence);
            var file = Path.Combine(evidenceRoot, item.EvidenceId.ToString("N") + ".evidence");
            var bytes = await File.ReadAllBytesAsync(file);
            bytes[^1] ^= 0x40;
            await File.WriteAllBytesAsync(file, bytes);
            var second = await auditor.InspectPendingAsync(key);
            Assert.False(second.SafeToAttemptDelivery);
            Assert.Contains(item.EvidenceId, second.CorruptPendingEvidence);
            File.Delete(file);
            var third = await auditor.InspectPendingAsync(key);
            Assert.Contains(item.EvidenceId, third.MissingPendingEvidence);
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }
}
