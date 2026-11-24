import base64
import hashlib
import json
import sys
import tempfile
import unittest
from email import policy
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gmail


class GmailTests(unittest.TestCase):
    def setUp(self):
        state = ROOT / ".state"
        state.mkdir(exist_ok=True, mode=0o700)
        self.temporary = tempfile.TemporaryDirectory(dir=state)
        self.root = Path(self.temporary.name)
        self.source = "<!doctype html>\n<html><body>Café • 漢字 &amp; exact spacing</body></html>\n".encode()
        original = self.root / "original.html"
        original.write_bytes(self.source)
        self.run = self.root / "run"
        self.run.mkdir()
        (self.run / "source.html").write_bytes(self.source)
        source_hash = hashlib.sha256(self.source).hexdigest()
        self.manifest = {"schemaVersion": 1, "runId": "fixture-run", "source": {"path": str(original), "sha256": source_hash, "bytes": len(self.source)},
                         "message": {"messageId": "<fixture-run@localpreview.invalid>", "subject": "[LocalPreview fixture-run]", "sourceHashHeader": "X-Source-Hash"},
                         "files": {"html": str(self.run / "source.html"), "eml": str(self.run / "message.eml")}, "clients": {}}
        (self.run / "manifest.json").write_text(json.dumps(self.manifest))
        message = EmailMessage(policy=policy.SMTP)
        message["Message-ID"] = self.manifest["message"]["messageId"]
        message["Subject"] = self.manifest["message"]["subject"]
        message["X-Source-Hash"] = source_hash
        message["X-LocalPreview-Run-ID"] = "fixture-run"
        message["MIME-Version"] = "1.0"
        message["Content-Type"] = 'text/html; charset="utf-8"'
        message["Content-Transfer-Encoding"] = "base64"
        message.set_payload(base64.encodebytes(self.source).decode())
        self.raw = message.as_bytes()
        (self.run / "message.eml").write_bytes(self.raw)

    def tearDown(self):
        self.temporary.cleanup()

    def test_insert_payload_preserves_complete_mime_and_utf8_html(self):
        metadata, raw = gmail.verified_message(self.run)
        payload = gmail.insert_payload(raw)
        decoded = base64.urlsafe_b64decode(payload["raw"] + "=" * (-len(payload["raw"]) % 4))
        self.assertEqual(decoded, self.raw)
        self.assertEqual(payload["labelIds"], ["INBOX", "UNREAD"])
        self.assertEqual(metadata["source"]["sha256"], hashlib.sha256(self.source).hexdigest())

    def test_changed_source_is_rejected_before_artifacts_are_created(self):
        Path(self.manifest["source"]["path"]).write_bytes(self.source + b"changed")
        with self.assertRaisesRegex(ValueError, "current email source changed"):
            gmail.prepare(self.run)
        self.assertFalse((self.run / "gmail").exists())

    def test_frozen_message_hash_rejects_changed_subject(self):
        self.manifest["files"]["emlSha256"] = hashlib.sha256(self.raw).hexdigest()
        (self.run / "manifest.json").write_text(json.dumps(self.manifest))
        gmail.verified_message(self.run)
        (self.run / "message.eml").write_bytes(
            self.raw.replace(b"Subject: [LocalPreview fixture-run]", b"Subject: changed")
        )
        with self.assertRaisesRegex(ValueError, "frozen message hash"):
            gmail.verified_message(self.run)

    def test_modified_mime_identity_or_body_is_rejected(self):
        eml = self.run / "message.eml"
        eml.write_bytes(self.raw.replace(b"fixture-run@localpreview.invalid", b"wrong-message@localpreview.invalid"))
        with self.assertRaisesRegex(ValueError, "Message-ID"):
            gmail.verified_message(self.run)
        eml.write_bytes(self.raw.replace(base64.b64encode(self.source[:3]), b"eHh4", 1))
        with self.assertRaisesRegex(ValueError, "MIME HTML body"):
            gmail.verified_message(self.run)

    def test_artifacts_use_received_time_and_only_return_safe_identity_fields(self):
        result = gmail.prepare(self.run)
        script = Path(result["requestScript"]).read_text()
        metadata = json.loads(Path(result["metadataFile"]).read_text())
        self.assertIn("internalDateSource=receivedTime", script)
        self.assertIn("messageId: response.ok ? data.id", script)
        self.assertNotIn("return data", script)
        self.assertNotIn("console.log", script)
        self.assertTrue(metadata["doesNotSendEmail"])
        self.assertIn("rfc822msgid%3A", metadata["gmailSearchUrl"])
        for path in result.values():
            self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)

    def test_unrelated_mailbox_labels_are_rejected(self):
        with self.assertRaises(ValueError):
            gmail.insert_payload(self.raw, ["TRASH"])


if __name__ == "__main__":
    unittest.main()
