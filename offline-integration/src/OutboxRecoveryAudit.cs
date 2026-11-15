using System.Security.Cryptography;

namespace IthuteSign.Modern.OfflineIntegration;

/// <summary>
/// Read-only recovery audit. It never silently requeues, deletes or uploads
/// orphaned evidence, because company/contract metadata must be authenticated.
/// </summary>
public sealed class OutboxRecoveryAudit
{
    private readonly string _evidenceDirectory;
    private readonly string _queueDirectory;

    public OutboxRecoveryAudit(string evidenceDirectory, string queueDirectory)
    {
        _evidenceDirectory = Path.GetFullPath(evidenceDirectory);
        _queueDirectory = Path.GetFullPath(queueDirectory);
    }

    public RecoveryAuditResult Inspect()
    {
        var evidence = ReadIds(_evidenceDirectory, ".evidence");
        var queued = ReadIds(_queueDirectory, ".queue");
        return new RecoveryAuditResult(
            evidence.Intersect(queued).OrderBy(x => x).ToArray(),
            evidence.Except(queued).OrderBy(x => x).ToArray(),
            queued.Except(evidence).OrderBy(x => x).ToArray());
    }

    private static HashSet<Guid> ReadIds(string directory, string extension)
    {
        var ids = new HashSet<Guid>();
        if (!Directory.Exists(directory)) return ids;
        foreach (var path in Directory.EnumerateFiles(directory, "*" + extension))
        {
            var filename = Path.GetFileNameWithoutExtension(path);
            if (!Guid.TryParseExact(filename, "N", out var id) || id == Guid.Empty || !ids.Add(id))
                throw new CryptographicException("Invalid or duplicated evidence identifier in recovery directory.");
            if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                throw new IOException("Recovery directory contains a link; manual review required.");
        }
        return ids;
    }
}

public sealed record RecoveryAuditResult(
    IReadOnlyList<Guid> MatchedEvidence,
    IReadOnlyList<Guid> OrphanedEvidence,
    IReadOnlyList<Guid> MissingEvidence);