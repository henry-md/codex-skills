#!/usr/bin/env python3
"""Prepare a verified Gmail INSERT request for execution through Chrome DevTools."""

import argparse
import base64
import hashlib
import json
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import quote

from oauth import file_input_script, write_private


INSERT_URI = "https://gmail.googleapis.com/gmail/v1/users/me/messages?internalDateSource=receivedTime"
INSERT_SCRIPT = """async () => {
  const input = document.querySelector('input[data-local-preview-payload="gmail-insert"]');
  if (!input?.files?.length) throw new Error('Upload the prepared Gmail insert JSON first.');
  const payload = JSON.parse(await input.files[0].text());
  const headers = {'Content-Type': 'application/json'};
  const token = globalThis.__localPreviewGoogleTokens?.access_token;
  if (token) headers.Authorization = 'Bearer ' + token;
  const response = await fetch('INSERT_URI', {
    method: 'POST', headers, body: JSON.stringify(payload), credentials: 'omit'
  });
  const data = await response.json();
  return {ok: response.ok, httpStatus: response.status,
          messageId: response.ok ? data.id : undefined,
          threadId: response.ok ? data.threadId : undefined,
          labelIds: response.ok ? data.labelIds : undefined};
}
""".replace("INSERT_URI", INSERT_URI)


def verified_message(run_dir):
    run_dir = Path(run_dir).resolve()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    source_hash = manifest["source"]["sha256"]
    source = (run_dir / "source.html").read_bytes()
    if hashlib.sha256(source).hexdigest() != source_hash:
        raise ValueError("The frozen HTML does not match the run manifest.")
    source_path = Path(manifest["source"]["path"])
    if not source_path.is_file() or hashlib.sha256(source_path.read_bytes()).hexdigest() != source_hash:
        raise ValueError("The current email source changed after this run was prepared.")
    raw = (run_dir / "message.eml").read_bytes()
    eml_hash = manifest.get("files", {}).get("emlSha256")
    if eml_hash is not None and hashlib.sha256(raw).hexdigest() != eml_hash:
        raise ValueError("The MIME message does not match the frozen message hash.")
    message = BytesParser(policy=policy.default).parsebytes(raw)
    if str(message.get("Message-ID", "")).strip() != manifest["message"]["messageId"]:
        raise ValueError("The MIME Message-ID does not match the run manifest.")
    if str(message.get("X-Source-Hash", "")).strip() != source_hash:
        raise ValueError("The MIME source-hash header does not match the run manifest.")
    if str(message.get("X-LocalPreview-Run-ID", "")).strip() != manifest["runId"]:
        raise ValueError("The MIME run ID does not match the run manifest.")
    html_parts = [part for part in message.walk() if part.get_content_type() == "text/html"
                  and part.get_content_disposition() != "attachment"]
    if len(html_parts) != 1 or html_parts[0].get_payload(decode=True) != source:
        raise ValueError("The MIME HTML body does not preserve the frozen source exactly.")
    return manifest, raw


def insert_payload(raw, labels=None):
    labels = list(dict.fromkeys(labels if labels is not None else ["INBOX", "UNREAD"]))
    if any(label not in {"INBOX", "UNREAD"} for label in labels):
        raise ValueError("Only INBOX and UNREAD labels are supported for preview insertion.")
    return {"raw": base64.urlsafe_b64encode(raw).decode().rstrip("="), "labelIds": labels}


def prepare(run_dir, output=None, labels=None):
    manifest, raw = verified_message(run_dir)
    output = Path(output) if output else Path(run_dir) / "gmail"
    payload = write_private(output / "insert-payload.json", insert_payload(raw, labels))
    setup = write_private(output / "setup-file-input.js", file_input_script("gmail-insert"))
    execute = write_private(output / "execute-insert.js", INSERT_SCRIPT)
    message_id = manifest["message"]["messageId"].strip("<>")
    metadata = {"runId": manifest["runId"], "sourceSHA256": manifest["source"]["sha256"],
                "messageId": manifest["message"]["messageId"], "subject": manifest["message"]["subject"],
                "insertUri": INSERT_URI, "doesNotSendEmail": True,
                "gmailSearchUrl": "https://mail.google.com/mail/u/0/#search/" + quote("rfc822msgid:" + message_id, safe="")}
    meta = write_private(output / "insert-metadata.json", metadata)
    return {"payloadFile": str(payload), "setupScript": str(setup), "requestScript": str(execute), "metadataFile": str(meta)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--run-dir", type=Path, required=True)
    prepare_parser.add_argument("--out-dir", type=Path)
    prepare_parser.add_argument("--label", action="append", choices=["INBOX", "UNREAD"])
    args = parser.parse_args()
    print(json.dumps(prepare(args.run_dir, args.out_dir, args.label)))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError)
              else "The Gmail preview artifacts could not be read or validated.", file=sys.stderr)
        raise SystemExit(1)
