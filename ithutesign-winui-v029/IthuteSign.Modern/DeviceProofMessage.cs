using System.Globalization;
using System.Text;

namespace IthuteSign.Modern;

/// <summary>
/// Exact LoanHub bridge proof transcript. The WinUI application never loads
/// an enrolled Ed25519 private key; a separately authenticated local bridge
/// must sign these bytes and return only the detached signature.
/// </summary>
public static class DeviceProofMessage
{
    public static byte[] Create(DeviceChallenge challenge, Guid companyId, Guid employeeId)
    {
        if (challenge is null || challenge.ChallengeId == Guid.Empty
            || challenge.WorkstationId == Guid.Empty || companyId == Guid.Empty
            || employeeId == Guid.Empty || !challenge.DeviceProofRequired
            || challenge.SigningAuthorized || challenge.ExpiresAt <= DateTimeOffset.UtcNow)
            throw new InvalidOperationException("Invalid or expired workstation challenge.");
        var nonce = challenge.Nonce ?? "";
        if (nonce.Length != 43 || nonce.Any(c => !(char.IsLetterOrDigit(c) || c is '-' or '_')))
            throw new InvalidOperationException("Invalid challenge nonce.");
        var decoded = Convert.FromBase64String(nonce.Replace('-', '+').Replace('_', '/') + "=");
        if (decoded.Length != 32 ||
            Convert.ToBase64String(decoded).TrimEnd('=').Replace('+', '-').Replace('/', '_') != nonce)
            throw new InvalidOperationException("Noncanonical challenge nonce.");
        var unixSeconds = challenge.ExpiresAt.ToUnixTimeSeconds().ToString(CultureInfo.InvariantCulture);
        var transcript = $"LOANHUB-WACOM-BRIDGE-DEVICE-V1\n{companyId:D}\n{employeeId:D}\n{challenge.WorkstationId:D}\n{challenge.ChallengeId:D}\n{nonce}\n{unixSeconds}\n";
        return Encoding.ASCII.GetBytes(transcript);
    }
}
