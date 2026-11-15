using System.Security.Cryptography;
using IthuteSign.Modern.OfflineIntegration;
using Xunit;

public sealed class EvidenceStoreTests
{
    [Fact]
    public async Task RoundTripAndTenantIsolation()
    {
        var folder = Path.Combine(Path.GetTempPath(), "ithute-evidence-test-" + Guid.NewGuid().ToString("N"));
        try
        {
            var store = new EncryptedEvidenceStore(folder);
            var key = RandomNumberGenerator.GetBytes(32);
            var evidence = Guid.NewGuid();
            var company = Guid.NewGuid();
            var contract = Guid.NewGuid();
            var payload = new byte[] { 0x25, 0x50, 0x44, 0x46, 0x2d, 0x31 };
            var path = await store.SaveAsync(evidence, company, contract, payload, key);
            Assert.Equal(-1, File.ReadAllBytes(path).AsSpan().IndexOf(payload));
            Assert.Equal(payload, await store.ReadAsync(evidence, company, contract, key));
            await Assert.ThrowsAsync<CryptographicException>(() =>
                store.ReadAsync(evidence, Guid.NewGuid(), contract, key));
            await Assert.ThrowsAsync<IOException>(() =>
                store.SaveAsync(evidence, company, contract, payload, key));
        }
        finally { if (Directory.Exists(folder)) Directory.Delete(folder, true); }
    }

    [Fact]
    public async Task TamperingIsDetected()
    {
        var folder = Path.Combine(Path.GetTempPath(), "ithute-evidence-test-" + Guid.NewGuid().ToString("N"));
        try
        {
            var store = new EncryptedEvidenceStore(folder);
            var key = RandomNumberGenerator.GetBytes(32);
            var evidence = Guid.NewGuid();
            var company = Guid.NewGuid();
            var contract = Guid.NewGuid();
            var path = await store.SaveAsync(evidence, company, contract, new byte[] { 1, 2, 3 }, key);
            var raw = await File.ReadAllBytesAsync(path);
            raw[^1] ^= 0x80;
            await File.WriteAllBytesAsync(path, raw);
            await Assert.ThrowsAsync<AuthenticationTagMismatchException>(() =>
                store.ReadAsync(evidence, company, contract, key));
        }
        finally { if (Directory.Exists(folder)) Directory.Delete(folder, true); }
    }
}
