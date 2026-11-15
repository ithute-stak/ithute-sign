using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace IthuteSign.Modern.OfflineIntegration;

/// <summary>
/// Encrypted, crash-recoverable metadata queue for a SINGLE running process.
/// Caller provides a protected 32-byte key and a server-verified delivery adapter.
/// Do not share this directory between running processes.
/// </summary>
public sealed class PersistentOutbox
{
    private readonly string _root;
    private readonly OfflineSyncCoordinator _sync;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private static readonly byte[] Prefix = "ITHUTE-OUTBOX-01"u8.ToArray();

    public PersistentOutbox(string root, OfflineSyncCoordinator sync)
    {
        _root = Path.GetFullPath(root);
        _sync = sync;
        Directory.CreateDirectory(_root);
    }

    public async Task<OutboxItem> EnqueueAsync(Guid companyId, Guid contractId,
        byte[] evidence, byte[] key, CancellationToken ct = default)
    {
        CheckKey(key);
        await _gate.WaitAsync(ct);
        try
        {
            var id = await _sync.StageAsync(companyId, contractId, evidence, key, ct);
            var item = new OutboxItem(id, companyId, contractId, 0, DateTimeOffset.UtcNow,
                null, false);
            await SaveAsync(item, key, ct);
            return item;
        }
        finally { _gate.Release(); }
    }

    public async Task<IReadOnlyList<OutboxItem>> PendingAsync(byte[] key,
        CancellationToken ct = default)
    {
        CheckKey(key);
        await _gate.WaitAsync(ct);
        try { return await LoadPendingAsync(key, ct); }
        finally { _gate.Release(); }
    }

    /// <summary>
    /// Run when the authenticated application starts or connectivity returns.
    /// Network ambiguity retains the item for later retry with the same ID.
    /// Only a verified matching receipt removes it from the pending set.
    /// </summary>
    public async Task<OutboxDrainResult> DrainAsync(byte[] key,
        IVerifiedEvidenceTransport transport, CancellationToken ct = default)
    {
        CheckKey(key);
        ArgumentNullException.ThrowIfNull(transport);
        await _gate.WaitAsync(ct);
        try
        {
            int delivered = 0, deferred = 0;
            foreach (var item in await LoadPendingAsync(key, ct))
            {
                ct.ThrowIfCancellationRequested();
                if (item.NextAttemptUtc > DateTimeOffset.UtcNow)
                {
                    deferred++;
                    continue;
                }
                try
                {
                    var receipt = await _sync.DeliverAsync(item.EvidenceId, item.CompanyId,
                        item.ContractId, key, transport, ct);
                    // Write receipt state durably. Do not delete encrypted evidence.
                    await SaveAsync(item with {
                        Delivered = true, ServerReceiptId = receipt.ServerReceiptId,
                        Attempts = item.Attempts + 1
                    }, key, ct);
                    delivered++;
                }
                catch (OperationCanceledException) when (ct.IsCancellationRequested)
                {
                    throw;
                }
                catch (Exception ex) when (ex is HttpRequestException or IOException
                    or TimeoutException or TaskCanceledException)
                {
                    int attempts = Math.Min(item.Attempts + 1, 100);
                    int delaySeconds = Math.Min(3600, 10 * (1 << Math.Min(attempts - 1, 8)));
                    await SaveAsync(item with {
                        Attempts = attempts,
                        NextAttemptUtc = DateTimeOffset.UtcNow.AddSeconds(delaySeconds)
                    }, key, ct);
                    deferred++;
                }
                // Invalid/mismatched receipts and cryptographic failures are not
                // swallowed: operator review is required before retry.
            }
            return new OutboxDrainResult(delivered, deferred);
        }
        finally { _gate.Release(); }
    }

    private async Task<List<OutboxItem>> LoadPendingAsync(byte[] key, CancellationToken ct)
    {
        var items = new List<OutboxItem>();
        foreach (var path in Directory.EnumerateFiles(_root, "*.queue").OrderBy(x => x))
        {
            ct.ThrowIfCancellationRequested();
            var item = await ReadAsync(path, key, ct);
            if (!Guid.TryParseExact(Path.GetFileNameWithoutExtension(path), "N", out var id)
                || id != item.EvidenceId)
                throw new CryptographicException("Outbox filename and metadata disagree.");
            if (!item.Delivered) items.Add(item);
        }
        return items;
    }

    private async Task SaveAsync(OutboxItem item, byte[] key, CancellationToken ct)
    {
        var path = Path.Combine(_root, item.EvidenceId.ToString("N") + ".queue");
        var tmp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        byte[] nonce = RandomNumberGenerator.GetBytes(12);
        byte[] plaintext = JsonSerializer.SerializeToUtf8Bytes(item);
        byte[] cipher = new byte[plaintext.Length];
        byte[] tag = new byte[16];
        try
        {
            using (var aes = new AesGcm(key, 16))
                aes.Encrypt(nonce, plaintext, cipher, tag, Prefix);
            await using (var stream = new FileStream(tmp, FileMode.CreateNew,
                FileAccess.Write, FileShare.None, 4096,
                FileOptions.Asynchronous | FileOptions.WriteThrough))
            {
                await stream.WriteAsync(Prefix, ct);
                await stream.WriteAsync(nonce, ct);
                await stream.WriteAsync(tag, ct);
                await stream.WriteAsync(cipher, ct);
                await stream.FlushAsync(ct);
            }
            File.Move(tmp, path, true);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plaintext);
            CryptographicOperations.ZeroMemory(cipher);
            if (File.Exists(tmp)) File.Delete(tmp);
        }
    }

    private static async Task<OutboxItem> ReadAsync(string path, byte[] key, CancellationToken ct)
    {
        var raw = await File.ReadAllBytesAsync(path, ct);
        int offset = Prefix.Length;
        if (raw.Length <= offset + 28 || raw.Length > 8192 ||
            !raw.AsSpan(0, offset).SequenceEqual(Prefix))
            throw new CryptographicException("Invalid outbox envelope.");
        var plaintext = new byte[raw.Length - offset - 28];
        try
        {
            using (var aes = new AesGcm(key, 16))
                aes.Decrypt(raw.AsSpan(offset, 12), raw.AsSpan(offset + 28),
                    raw.AsSpan(offset + 12, 16), plaintext, Prefix);
            var item = JsonSerializer.Deserialize<OutboxItem>(plaintext)
                ?? throw new CryptographicException("Missing outbox record.");
            if (item.EvidenceId == Guid.Empty || item.CompanyId == Guid.Empty ||
                item.ContractId == Guid.Empty || item.Attempts < 0 ||
                (item.Delivered && string.IsNullOrWhiteSpace(item.ServerReceiptId)))
                throw new CryptographicException("Invalid outbox record.");
            return item;
        }
        finally { CryptographicOperations.ZeroMemory(plaintext); }
    }

    private static void CheckKey(byte[] key)
    {
        if (key is null || key.Length != 32) throw new ArgumentException("AES-256 key required.");
    }
}

public sealed record OutboxItem(Guid EvidenceId, Guid CompanyId, Guid ContractId,
    int Attempts, DateTimeOffset NextAttemptUtc, string? ServerReceiptId, bool Delivered);
public sealed record OutboxDrainResult(int Delivered, int Deferred);
