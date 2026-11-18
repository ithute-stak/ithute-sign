"""Send offline-signed contracts using an explicitly configured iMail SMTP server.

Credentials are used for this send only, never stored in application files.
SMTP acceptance does not establish final inbox delivery.
"""
import smtplib
import re
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

MAX_PDF_BYTES = 20 * 1024 * 1024
SENDER = "documents@batlokoa.co.ls"


def validate_recipient(value):
    value = value.strip()
    parsed_name, address = parseaddr(value)
    if (not address or parsed_name or address != value or value.count("@") != 1
            or any(c.isspace() for c in value) or "\r" in value or "\n" in value
            or len(value) > 254 or "." not in value.rsplit("@", 1)[-1]
            or not re.fullmatch(r"[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", value)):
        raise ValueError("Enter a valid client email address")
    return address


def send_signed_pdf(host, port, security, username, password, recipient, pdf_path, reference):
    """Submit a signed PDF via authenticated SMTP over verified TLS."""
    host = host.strip()
    if (not host or any(c.isspace() for c in host) or "/" in host or "@" in host
            or ":" in host or "\\" in host or host.startswith(".")):
        raise ValueError("Configure the iMail SMTP hostname")
    if not isinstance(port, int) or port not in (465, 587):
        raise ValueError("Use SMTP port 465 (SSL) or 587 (STARTTLS)")
    if (port, security) not in ((465, "ssl"), (587, "starttls")):
        raise ValueError("SMTP security must match its port")
    if username.strip().lower() != SENDER or not password:
        raise ValueError("Authenticate with the documents@batlokoa.co.ls mailbox")
    recipient = validate_recipient(recipient)
    reference = reference.strip()
    if not reference or len(reference) > 100 or "\r" in reference or "\n" in reference:
        raise ValueError("Enter a valid contract reference")
    path = Path(pdf_path)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError("Save the signed PDF before emailing")
    size = path.stat().st_size
    if not 100 <= size <= MAX_PDF_BYTES:
        raise ValueError("Signed PDF is empty or exceeds 20 MiB")
    pdf = path.read_bytes()
    if not pdf.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF file")
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = recipient
    msg["Subject"] = "Batlokoa Financial Services - Signed contract " + reference
    msg.set_content(
        "Dear Client,\n\nPlease find your signed contract attached.\n"
        "Contract reference: " + reference + "\n\n"
        "Regards,\nBatlokoa Financial Services\n"
    )
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=path.name)
    context = ssl.create_default_context()
    if security == "ssl":
        with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as smtp:
            smtp.login(SENDER, password)
            refused = smtp.send_message(msg, from_addr=SENDER, to_addrs=[recipient])
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(SENDER, password)
            smtp.send_message(msg, from_addr=SENDER, to_addrs=[recipient])
    return recipient
