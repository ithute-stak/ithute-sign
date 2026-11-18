"""Tests for iMail validation and TLS SMTP submission; no network required."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from imail_delivery import send_signed_pdf, validate_recipient


@pytest.mark.parametrize("address", ["", "invalid", "a@b", "Name <a@b.co>", "a@b.co\r\nBcc:evil@x.co"])
def test_invalid_recipient(address):
    with pytest.raises(ValueError):
        validate_recipient(address)


def test_imail_ssl_submission(tmp_path):
    pdf = tmp_path / "contract.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + b" " * 120)
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp.send_message.return_value = {}  # SMTP accepted all recipients
    with patch("imail_delivery.smtplib.SMTP_SSL", return_value=smtp) as factory:
        recipient = send_signed_pdf(
            "mail.example.com", 465, "ssl", "documents@batlokoa.co.ls",
            "temporary-password", "client@example.com", pdf, "CONTRACT-1"
        )
    assert recipient == "client@example.com"
    factory.assert_called_once()
    smtp.login.assert_called_once_with("documents@batlokoa.co.ls", "temporary-password")
    msg = smtp.send_message.call_args.args[0]
    assert msg["From"] == "documents@batlokoa.co.ls"
    assert msg["To"] == "client@example.com"
    assert len(list(msg.iter_attachments())) == 1


def test_imail_rejects_plaintext_smtp(tmp_path):
    with pytest.raises(ValueError):
        send_signed_pdf("mail.example.com", 25, "none",
            "documents@batlokoa.co.ls", "password", "client@example.com",
            tmp_path / "missing.pdf", "REF")
