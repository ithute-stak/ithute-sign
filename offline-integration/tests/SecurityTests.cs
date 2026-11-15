using System.Net;
using System.Text;
using IthuteSign.Modern.OfflineIntegration;
using Xunit;
public class SecurityTests {
 [Fact] public void RejectsHttp() => Assert.Throws<ArgumentException>(()=>new ContractReviewClient(new Uri("http://127.0.0.1:8767/")));
 [Fact] public async Task RequiresBridge() { using var c=new ContractReviewClient(new Uri("https://api.loanhub.co.ls/"),new Fake(HttpStatusCode.OK,"{}")); await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>c.DiscoverAsync(Guid.NewGuid(),Guid.NewGuid(),"employee","")); }
 [Fact] public async Task RejectsOtherBorrower() { using var c=new ContractReviewClient(new Uri("https://api.loanhub.co.ls/"),new Fake(HttpStatusCode.OK,"{\"borrower_id\":\""+Guid.NewGuid()+"\",\"signing_authorized\":false,\"contract_signed\":false,\"contracts\":[]}")); await Assert.ThrowsAsync<InvalidDataException>(()=>c.DiscoverAsync(Guid.NewGuid(),Guid.NewGuid(),"employee","bridge")); }
 [Fact] public void EvidenceIsNotFinalization() { var s=new SigningStateMachine(); s.Login(Guid.NewGuid());s.SelectLoan(s.CompanyId,Guid.NewGuid());s.VerifyWorkstation(true);s.ContractsRetrieved(true);var contract=Guid.NewGuid();s.PreparedIntent(contract,true);s.RecordConsent(true);s.CaptureEvidence(true);Assert.False(s.IsSigned);Assert.Throws<UnauthorizedAccessException>(()=>s.FinalizeFromServer(false,contract));s.FinalizeFromServer(true,contract);Assert.True(s.IsSigned); }
 private sealed class Fake(HttpStatusCode status,string json):HttpMessageHandler { protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage req,CancellationToken ct)=>Task.FromResult(new HttpResponseMessage(status){Content=new StringContent(json,Encoding.UTF8,"application/json")}); }
}
