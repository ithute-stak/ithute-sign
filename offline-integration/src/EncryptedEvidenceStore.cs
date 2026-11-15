using System.Security.Cryptography;
using System.Text;

namespace IthuteSign.Modern.OfflineIntegration;

/// <summary>
/// Offline encrypted evidence storage. Caller must provision and protect the
/// 256-bit key using an approved Windows workstation key management mechanism.
/// This class deliberately does not persist the key or claim a document signed.
/// </summary>
public sealed class EncryptedEvidenceStore
{
    private static readonly byte[] Magic = "ITHUTE-EVIDENCE-01"u8.ToArray();
    private readonly string _root;

    public EncryptedEvidenceStore(string root)
    {
        if (string.IsNullOrWhiteSpace(root))
            throw new ArgumentException("Evidence directory required.", nameof(root));
        _root = Path.GetFullPath(root);
        Directory.CreateDirectory(_root);
    }

    public Task<string> SaveAsync(Guid evidenceId, Guid companyId,
        Guid contractId, ReadOnlyMemory<byte> pdfOrEvidence,
        ReadOnlyMemory<byte> key, CancellationToken ct = default)
    {
        if (evidenceId == Guid.Empty || companyId == Guid.Empty || contractId == Guid.Empty)
            throw new ArgumentException("Nonempty evidence, company and contract IDs required.");
        if (key.Length != 32) throw new ArgumentException("AES-256 key required.");
        if (pdfOrEvidence.Length == 0 || pdfOrEvidence.Length > 25 * 1024 * 1024)
            throw new ArgumentException("Evidence size must be between 1 byte and 25 MiB.");

        var path = Path.Combine(_root, evidenceId.ToString("N") + ".evidence");
        if (File.Exists(path)) throw new IOException("Evidence ID already exists.");
        byte[] nonce = RandomNumberGenerator.GetBytes(12);
        byte[] cipher = new byte[pdfOrEvidence.Length];
        byte[] tag = new byte[16];
        byte[] aad = Metadata(evidenceId, companyId, contractId);
        using (var aes = new AesGcm(key.Span, 16))
            aes.Encrypt(nonce, pdfOrEvidence.Span, cipher, tag, aad);

        // Exclusive create prevents overwriting evidence under a reused ID.
        // Write-through and flush minimize crash windows. Failed writes are deleted.
        try
        {
            using var stream = new FileStream(path, FileMode.CreateNew,
                FileAccess.Write, FileShare.None, 81920, FileOptions.WriteThrough);
            ct.ThrowIfCancellationRequested();
            stream.Write(Magic);
            stream.Write(aad);
            stream.Write(nonce);
            stream.Write(tag);
            stream.Write(cipher);
            stream.Flush(true);
        }
        catch
        {
            try { File.Delete(path); } catch { }
            throw;
        }
        CryptographicOperations.ZeroMemory(cipher);
        return Task.FromResult(path);
    }

    public Task<byte[]> ReadAsync(Guid evidenceId, Guid companyId,
        Guid contractId, ReadOnlyMemory<byte> key, CancellationToken ct = default)
    {
        if (key.Length != 32) throw new ArgumentException("AES-256 key required.");
        if (evidenceId == Guid.Empty || companyId == Guid.Empty || contractId == Guid.Empty)
            throw new ArgumentException("Nonempty IDs required.");
        var path = Path.Combine(_root, evidenceId.ToString("N") + ".evidence");
        ct.ThrowIfCancellationRequested();
        var raw = File.ReadAllBytes(path);
        var aad = Metadata(evidenceId, companyId, contractId);
        int header = Magic.Length + aad.Length + 12 + 16;
        if (raw.Length <= header || raw.Length > header + 25 * 1024 * 1024 ||
            !raw.AsSpan(0, Magic.Length).SequenceEqual(Magic) ||
            !raw.AsSpan(Magic.Length, aad.Length).SequenceEqual(aad))
            throw new CryptographicException("Evidence envelope mismatch.");
        int offset = Magic.Length + aad.Length;
        byte[] plaintext = new byte[raw.Length - header];
        using (var aes = new AesGcm(key.Span, 16))
            aes.Decrypt(raw.AsSpan(offset, 12), raw.AsSpan(header),
                raw.AsSpan(offset + 12, 16), plaintext, aad);
        return Task.FromResult(plaintext);
    }

    private static byte[] Metadata(Guid evidenceId, Guid companyId, Guid contractId) =>
        Encoding.ASCII.GetBytes($"{evidenceId:N}{companyId:N}{contractId:N}");
}
