# Ithute Mailbox Products integration — Batlokoa

IthuteSign uses the existing Ithute-hosted mailbox `documents@batlokoa.co.ls` for outgoing signed PDF contracts. It does **not** create a second mailbox or modify the Ithute mail deployment.

## Operator configuration

1. Obtain the **actual SMTP submission hostname** from the deployed Ithute Mailbox Products configuration. Do not infer the hostname from the domain or MX record.
2. Confirm that mailbox SMTP authentication is enabled for `documents@batlokoa.co.ls`, and whether submission uses port 465 (implicit TLS) or port 587 (STARTTLS).
3. On the signing workstation, set `ITHUTESIGN_IMAIL_SMTP_HOST` to the confirmed hostname, for example:
   `export ITHUTESIGN_IMAIL_SMTP_HOST='YOUR-VERIFIED-SMTP-HOST'`
4. Launch `python app/main.py`. Sign and save a contract, then choose **Email signed PDF via iMail**.
5. Enter the client's verified email address, contract reference, and the mailbox password in the dialog. The application does not persist the password.
6. First send to a mailbox you control, inspect the received PDF, and check the Ithute mail logs and recipient inbox. SMTP acceptance alone does not guarantee delivery.

**Security:** Never commit mailbox passwords, service tokens, or live customer contracts to GitHub. Do not use unauthenticated SMTP or disable TLS certificate verification. A workstation mailbox password grants mailbox-level sending authority: use a dedicated credential, employee controls, and server-side audit before broad deployment. Existing checks bind the selected PDF to the saved local file hash, but do not cryptographically prove the signer's identity.

**Current status:** SMTP submission code and mocked tests exist. The production hostname, mailbox authentication, and end-to-end delivery have not been independently verified.
