namespace IthuteSign.Modern.OfflineIntegration;
public enum SigningStage { LoggedOut, EmployeeAuthenticated, LoanSelected, WorkstationVerified, ContractsLoaded, IntentPrepared, ConsentRecorded, EvidenceCaptured, ServerFinalized }
public sealed class SigningStateMachine {
 public SigningStage Stage { get; private set; }
 public Guid CompanyId { get; private set; }
 public Guid BorrowerId { get; private set; }
 public Guid ContractId { get; private set; }
 public bool IsSigned => Stage == SigningStage.ServerFinalized;
 public void Login(Guid company) { Reset(); if(company==Guid.Empty) throw new ArgumentException("Invalid company"); CompanyId=company; Stage=SigningStage.EmployeeAuthenticated; }
 public void SelectLoan(Guid company, Guid borrower) { Require(SigningStage.EmployeeAuthenticated); if(company!=CompanyId || borrower==Guid.Empty) throw new UnauthorizedAccessException(); BorrowerId=borrower; Stage=SigningStage.LoanSelected; }
 public void VerifyWorkstation(bool serverVerified) { Require(SigningStage.LoanSelected); if(!serverVerified) throw new UnauthorizedAccessException(); Stage=SigningStage.WorkstationVerified; }
 public void ContractsRetrieved(bool serverAuthorized) { Require(SigningStage.WorkstationVerified); if(!serverAuthorized) throw new UnauthorizedAccessException(); Stage=SigningStage.ContractsLoaded; }
 public void PreparedIntent(Guid contract, bool serverConfirmed) { Require(SigningStage.ContractsLoaded); if(!serverConfirmed || contract==Guid.Empty) throw new UnauthorizedAccessException(); ContractId=contract; Stage=SigningStage.IntentPrepared; }
 public void RecordConsent(bool explicitConsent) { Require(SigningStage.IntentPrepared); if(!explicitConsent) throw new UnauthorizedAccessException(); Stage=SigningStage.ConsentRecorded; }
 public void CaptureEvidence(bool verified) { Require(SigningStage.ConsentRecorded); if(!verified) throw new InvalidOperationException(); Stage=SigningStage.EvidenceCaptured; }
 public void FinalizeFromServer(bool confirmed, Guid contract) { Require(SigningStage.EvidenceCaptured); if(!confirmed || contract!=ContractId) throw new UnauthorizedAccessException(); Stage=SigningStage.ServerFinalized; }
 public void Reset() { Stage=SigningStage.LoggedOut; CompanyId=BorrowerId=ContractId=Guid.Empty; }
 private void Require(SigningStage expected) { if(Stage!=expected) throw new InvalidOperationException($"Expected {expected}; current {Stage}"); }
}