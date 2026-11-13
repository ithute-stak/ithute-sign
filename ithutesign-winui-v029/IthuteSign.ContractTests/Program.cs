using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using IthuteSign.Modern;

var borrower = Guid.NewGuid();
var company = Guid.NewGuid();
var contract = Guid.NewGuid();
var file = Guid.NewGuid();
var workstation = Guid.NewGuid();
var intentId = Guid.NewGuid();
var pdf = Encoding.ASCII.GetBytes("%PDF-1.7\nOriginal loan contract bytes\n%%EOF");
var sha = Convert.ToHexString(SHA256.HashData(pdf)).ToLowerInvariant();
var prepared = new PreparedLoanHubIntent {
    IntentId = intentId, CompanyId = company, BorrowerId = borrower, ContractId = contract,
    DocumentVersion = "1", DocumentSha256 = sha, Status = "prepared",
    ExpiresAt = DateTimeOffset.UtcNow.AddMinutes(5)
};
var calls = 0;
using var http = new HttpClient(new FakeHandler(request => {
    calls++;
    Assert(request.RequestUri?.Scheme == "https", "TLS origin");
    Assert(request.Headers.Authorization?.Scheme == "Bearer", "Bearer authorization");
    Assert(request.Headers.GetValues("X-Company-ID").Single() == company.ToString("D"), "company isolation");
    Assert(request.Headers.GetValues("X-Wacom-Bridge-Session").Single() == "wb1_test", "workstation proof");
    var path = request.RequestUri!.AbsolutePath;
    if (path.EndsWith("/eligible-contracts"))
        return Json(new { borrower_id = borrower, contracts = new [] { new {
            borrower_id = borrower, contract_id = contract, contract_number = "L-1",
            source_file_id = file, document_version = "1" } },
            signing_authorized = false, contract_signed = false });
    if (path.EndsWith("/source-pdf")) {
        var response = new HttpResponseMessage(HttpStatusCode.OK) {
            Content = new ByteArrayContent(pdf) };
        response.Content.Headers.ContentType = new("application/pdf");
        response.Headers.Add("X-Wacom-Original-SHA256", sha);
        response.Headers.Add("X-Wacom-Signing-Authorized", "false");
        return response;
    }
    if (path.EndsWith("/consent"))
        return Json(new { intent_id = intentId, status = "consented", company_id = company,
            borrower_id = borrower, contract_id = contract, document_version = "1",
            document_sha256 = sha, expires_at = prepared.ExpiresAt, signing_authorized = false,
            signed_contract_created = false, signature_reuse_allowed = false });
    if (path.EndsWith("/wacom-document-intents"))
        return Json(new { intent_id = intentId, status = "prepared", company_id = company,
            borrower_id = borrower, contract_id = contract, document_version = "1",
            document_sha256 = sha, expires_at = prepared.ExpiresAt, signing_authorized = false,
            signed_contract_created = false, signature_reuse_allowed = false }, HttpStatusCode.Created);
    throw new InvalidOperationException("Unexpected API path " + path);
})) { BaseAddress = new Uri("https://loanhub.example/") };

var contracts = await new LoanHubContractDiscovery(http)
    .GetEligibleContractsAsync(borrower, company, "test-token", "wb1_test");
Assert(contracts.Count == 1 && contracts[0].ContractId == contract, "eligible contracts");
var created = await new LoanHubDocumentIntentClient(http)
    .PrepareAsync(contracts[0], company, workstation, "test-token", "wb1_test");
Assert(created.IntentId == intentId, "intent preparation");
var actual = await new LoanHubOriginalContractReader(http)
    .ReadOriginalPdfAsync(created, company, "test-token", "wb1_test");
Assert(actual.SequenceEqual(pdf), "original PDF preserved byte for byte");
var consent = await new LoanHubDocumentConsentClient(http)
    .RecordConsentAsync(created, company, "I reviewed this contract", "CONSENT-TEST-001",
        sha, "test-token", "wb1_test");
Assert(consent.Status == "consented", "consent transition");
await Reject(async () => await new LoanHubDocumentConsentClient(http)
    .RecordConsentAsync(created, company, "yes", "CONSENT-TEST-002",
        new string('0', 64), "test-token", "wb1_test"), "changed PDF rejected");
await Reject(async () => await new LoanHubDocumentIntentClient(http)
    .PrepareAsync(contracts[0], company, workstation, "", "wb1_test"), "missing token rejected");
Assert(calls == 4, "invalid requests rejected before network");
Console.WriteLine("PASS: exact contract discovery, preparation, original PDF verification, consent and negative checks.");

static HttpResponseMessage Json(object data, HttpStatusCode status = HttpStatusCode.OK) =>
    new(status) { Content = new StringContent(JsonSerializer.Serialize(data), Encoding.UTF8, "application/json") };
static void Assert(bool value, string name) {
    if (!value) throw new Exception("FAILED: " + name);
}
static async Task Reject(Func<Task> action, string name) {
    try { await action(); } catch (ArgumentException) { return; }
    catch (InvalidOperationException) { return; }
    catch (UnauthorizedAccessException) { return; }
    throw new Exception("FAILED: " + name);
}
sealed class FakeHandler(Func<HttpRequestMessage, HttpResponseMessage> responder) : HttpMessageHandler {
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token) =>
        Task.FromResult(responder(request));
}
