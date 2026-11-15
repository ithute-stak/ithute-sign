using IthuteSign.Modern.OfflineIntegration;
using Xunit;

public sealed class OutboxRecoveryAuditTests
{
    [Fact]
    public void ReportsOrphanedAndMissingEvidenceWithoutModifyingFiles()
    {
        var root = Path.Combine(Path.GetTempPath(), "ithute-recovery-" + Guid.NewGuid().ToString("N"));
        var evidence = Path.Combine(root, "evidence");
        var queue = Path.Combine(root, "queue");
        Directory.CreateDirectory(evidence);
        Directory.CreateDirectory(queue);
        try
        {
            var matched = Guid.NewGuid();
            var orphan = Guid.NewGuid();
            var missing = Guid.NewGuid();
            foreach (var id in new[] { matched, orphan })
                File.WriteAllBytes(Path.Combine(evidence, id.ToString("N") + ".evidence"), new byte[] { 1 });
            foreach (var id in new[] { matched, missing })
                File.WriteAllBytes(Path.Combine(queue, id.ToString("N") + ".queue"), new byte[] { 2 });
            var result = new OutboxRecoveryAudit(evidence, queue).Inspect();
            Assert.Equal(new[] { matched }, result.MatchedEvidence);
            Assert.Equal(new[] { orphan }, result.OrphanedEvidence);
            Assert.Equal(new[] { missing }, result.MissingEvidence);
            Assert.Equal(4, Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories).Count());
        }
        finally { Directory.Delete(root, true); }
    }
}
