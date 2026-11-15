using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
namespace IthuteSign.Modern.OfflineIntegration;
public sealed class ContractReviewClient : IDisposable {
 private readonly HttpClient http;
 public ContractReviewClient(Uri origin, HttpMessageHandler? handler=null) {
  if(!origin.IsAbsoluteUri || origin.Scheme!="https" || origin.UserInfo!="" || origin.Query!="" || origin.Fragment!="") throw new ArgumentException("Clean HTTPS origin required");
  http=handler is null ? new HttpClient(new HttpClientHandler { AllowAutoRedirect=false, UseCookies=false }) : new HttpClient(handler);
  http.BaseAddress=new Uri(origin.AbsoluteUri.TrimEnd('/')+"/");
  http.Timeout=TimeSpan.FromSeconds(20);
 }
 public async Task<IReadOnlyList<ContractChoice>> DiscoverAsync(Guid company,Guid borrower,string bearer,string bridge,CancellationToken ct=default) {
  if(company==Guid.Empty || borrower==Guid.Empty || !Valid(bearer) || !Valid(bridge)) throw new UnauthorizedAccessException("Valid company, borrower and verified bridge session required");
  using var req=new HttpRequestMessage(HttpMethod.Get,$"api/v1/wacom-document-intents/borrowers/{borrower:D}/eligible-contracts");
  req.Headers.Authorization=new AuthenticationHeaderValue("Bearer",bearer);
  req.Headers.Add("X-Company-ID",company.ToString("D"));
  req.Headers.Add("X-Wacom-Bridge-Session",bridge);
  using var resp=await http.SendAsync(req,HttpCompletionOption.ResponseHeadersRead,ct);
  if(resp.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden) throw new UnauthorizedAccessException("LoanHub denied access");
  if(!resp.IsSuccessStatusCode) throw new HttpRequestException("Contract discovery failed",null,resp.StatusCode);
  var result=await resp.Content.ReadFromJsonAsync<ContractPayload>(cancellationToken:ct);
  if(result is null || result.BorrowerId!=borrower || result.SigningAuthorized || result.ContractSigned || result.Contracts is null || result.Contracts.Count>50 || result.Contracts.Select(x=>x.ContractId).Distinct().Count()!=result.Contracts.Count || result.Contracts.Any(x=>x.BorrowerId!=borrower || x.ContractId==Guid.Empty || x.SourceFileId==Guid.Empty || string.IsNullOrWhiteSpace(x.DocumentVersion) || x.DocumentVersion.Length>80 || x.DocumentVersion.Any(char.IsControl))) throw new InvalidDataException("Invalid or unscoped contract choices");
  return result.Contracts.AsReadOnly();
 }
 private static bool Valid(string? s)=>!string.IsNullOrWhiteSpace(s) && s.Length<=4096 && s.All(c=>c>=0x21 && c<=0x7e);
 public void Dispose()=>http.Dispose();
 private sealed class ContractPayload {
  [JsonPropertyName("borrower_id")] public Guid BorrowerId {get;set;}
  [JsonPropertyName("signing_authorized")] public bool SigningAuthorized {get;set;}
  [JsonPropertyName("contract_signed")] public bool ContractSigned {get;set;}
  [JsonPropertyName("contracts")] public List<ContractChoice>? Contracts {get;set;}
 }
}
public sealed class ContractChoice {
 [JsonPropertyName("borrower_id")] public Guid BorrowerId {get;set;}
 [JsonPropertyName("contract_id")] public Guid ContractId {get;set;}
 [JsonPropertyName("source_file_id")] public Guid SourceFileId {get;set;}
 [JsonPropertyName("document_version")] public string? DocumentVersion {get;set;}
}
