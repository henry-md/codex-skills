#!/usr/bin/env python3
"""Prepare Google desktop OAuth artifacts and receive a private loopback callback."""

import argparse
import base64
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

BASE = Path(__file__).resolve().parent
DEFAULT_STATE = BASE / ".state" / "oauth"
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
DOWNLOAD_AUTH_URIS = {AUTH_URI, "https://accounts.google.com/o/oauth2/auth"}
TOKEN_URI = "https://oauth2.googleapis.com/token"
INSERT_SCOPE = "https://www.googleapis.com/auth/gmail.insert"
ALLOWED_SCOPES = {INSERT_SCOPE, "https://www.googleapis.com/auth/gmail.readonly"}


def write_private(path, value):
    """Write private state atomically without exposing a partly written credential file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if isinstance(value, (dict, list)):
        value = json.dumps(value, indent=2) + "\n"
    if isinstance(value, str):
        value = value.encode()
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def read_private(path, as_json=True):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise ValueError("Private input files must have owner-only permissions (mode 0600).")
    text = path.read_text()
    return json.loads(text) if as_json else text


def import_client(download, destination):
    download = Path(download)
    if download.is_symlink():
        raise ValueError("Use the downloaded desktop client file directly, not a symbolic link.")
    download.chmod(0o600)
    data = read_private(download)
    client = data.get("installed") if isinstance(data, dict) else None
    if not isinstance(client, dict) or not isinstance(client.get("client_id"), str):
        raise ValueError("The input must be a Google OAuth desktop-client download with an installed section.")
    if client.get("auth_uri", AUTH_URI) not in DOWNLOAD_AUTH_URIS or client.get("token_uri", TOKEN_URI) != TOKEN_URI:
        raise ValueError("The desktop client does not use the expected Google authorization endpoints.")
    normalized = {"client_id": client["client_id"], "auth_uri": AUTH_URI, "token_uri": TOKEN_URI}
    if client.get("client_secret"):
        normalized["client_secret"] = client["client_secret"]
    write_private(destination, normalized)
    return normalized


def validate_redirect(uri):
    parts = urlsplit(uri)
    try:
        port = parts.port
    except ValueError:
        raise ValueError("Use an HTTP loopback redirect with a valid port.") from None
    if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "::1"}
            or not port or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError("Use an HTTP loopback redirect with an explicit port and no query or fragment.")
    return uri


def code_challenge(verifier):
    if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
        raise ValueError("The PKCE verifier must contain 43 to 128 unreserved characters.")
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")


def authorization_session(client, redirect_uri, scopes=None, now=None, verifier=None, state=None):
    validate_redirect(redirect_uri)
    scopes = list(dict.fromkeys(scopes or [INSERT_SCOPE]))
    if not scopes or any(scope not in ALLOWED_SCOPES for scope in scopes):
        raise ValueError("Only Gmail insertion and optional read-only verification scopes are supported.")
    now = time.time() if now is None else now
    verifier = verifier or secrets.token_urlsafe(64)
    state = state or secrets.token_urlsafe(32)
    session = {"schemaVersion": 1, "clientId": client["client_id"], "redirectUri": redirect_uri,
               "scopes": scopes, "codeVerifier": verifier, "state": state,
               "createdAtUnix": now, "expiresAtUnix": now + 900}
    parameters = {"client_id": client["client_id"], "redirect_uri": redirect_uri,
                  "response_type": "code", "scope": " ".join(scopes), "access_type": "offline",
                  "prompt": "consent", "state": state,
                  "code_challenge": code_challenge(verifier), "code_challenge_method": "S256"}
    return session, AUTH_URI + "?" + urlencode(parameters)


def callback_values(session, callback_url, now=None):
    now = time.time() if now is None else now
    if session.get("expiresAtUnix", 0) < now:
        raise ValueError("The authorization session expired; prepare a new authorization request.")
    parts = urlsplit(callback_url.strip())
    redirect = urlsplit(validate_redirect(session["redirectUri"]))
    if (parts.scheme, parts.netloc, parts.path) != (redirect.scheme, redirect.netloc, redirect.path) or parts.fragment:
        raise ValueError("The callback did not use the authorization session's loopback redirect.")
    try:
        values = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise ValueError("The callback query could not be parsed.") from None
    returned_state = values.get("state", [])
    if len(returned_state) != 1 or not hmac.compare_digest(returned_state[0], session["state"]):
        raise ValueError("The authorization callback state did not match.")
    if "error" in values:
        if len(values["error"]) != 1 or not values["error"][0] or "code" in values:
            raise ValueError("The authorization callback did not contain one response.")
    elif len(values.get("code", [])) != 1 or not values["code"][0]:
        raise ValueError("The authorization callback did not contain one code.")
    return values


def exchange_fields(client, session, callback_url, now=None):
    if session.get("clientId") != client.get("client_id"):
        raise ValueError("The authorization session belongs to a different OAuth client.")
    values = callback_values(session, callback_url, now)
    if "error" in values:
        raise ValueError("Google authorization was declined or could not be completed.")
    fields = {"client_id": client["client_id"], "code": values["code"][0],
              "code_verifier": session["codeVerifier"], "grant_type": "authorization_code",
              "redirect_uri": session["redirectUri"]}
    if client.get("client_secret"):
        fields["client_secret"] = client["client_secret"]
    return fields


def listen(state_dir=DEFAULT_STATE, port=0, path="/oauth/callback", timeout=900, runtime_dir=None):
    if not 0 <= port <= 65535 or not 0 < timeout <= 900:
        raise ValueError("Use a port from 0 to 65535 and a timeout above zero up to 900 seconds.")
    if not re.fullmatch(r"/[A-Za-z0-9/_-]+", path) or path.startswith("//"):
        raise ValueError("Use an absolute callback path containing letters, digits, slash, underscore or hyphen.")
    state_dir = Path(state_dir).expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_dir.chmod(0o700)
    runtime = Path(runtime_dir).expanduser().resolve() if runtime_dir else state_dir / ("listener-" + uuid.uuid4().hex)
    runtime.mkdir(parents=True, mode=0o700)
    runtime.chmod(0o700)
    session_file, callback_file, ready_file = (runtime / name for name in ("session.json", "callback.txt", "ready.json"))

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, text):
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            target = urlsplit(self.path)
            if len(self.path) > 16384 or target.scheme or target.netloc or target.fragment or target.path != path:
                self.reply(404, "This is not the authorization callback path.")
                return
            try:
                session = read_private(session_file)
                if session.get("redirectUri") != redirect_uri:
                    raise ValueError("The authorization session belongs to another listener.")
                callback = redirect_uri + ("?" + target.query if target.query else "")
                values = callback_values(session, callback)
            except (OSError, ValueError, KeyError, TypeError):
                self.reply(400, "The authorization callback was not accepted.")
                return
            write_private(callback_file, callback + "\n")
            server.authorization_error = "error" in values
            server.callback_received = True
            self.reply(200, "Authorization response received. You can close this window.")

    class LoopbackServer(HTTPServer):
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(min(1, timeout))
            return connection, address

        def handle_error(self, request, client_address):
            # Request URLs can contain codes; never let the server print them.
            pass

    with LoopbackServer(("127.0.0.1", port), CallbackHandler) as server:
        server.callback_received = False
        server.authorization_error = False
        redirect_uri = f"http://127.0.0.1:{server.server_port}{path}"
        info = {"redirectUri": redirect_uri, "sessionFile": str(session_file),
                "callbackFile": str(callback_file), "readyFile": str(ready_file), "status": "listening"}
        write_private(ready_file, info)
        print(json.dumps(info), flush=True)
        deadline = time.monotonic() + timeout
        while not server.callback_received and time.monotonic() < deadline:
            server.timeout = max(0, min(0.2, deadline - time.monotonic()))
            server.handle_request()
        info["status"] = ("declined" if server.authorization_error else "captured") if server.callback_received else "timed-out"
        write_private(ready_file, info)
        if not server.callback_received:
            raise ValueError("The loopback listener timed out without a valid authorization callback.")
        return info


def refresh_fields(client, tokens):
    if tokens.get("client_id") not in {None, client["client_id"]}:
        raise ValueError("The saved tokens belong to a different OAuth client.")
    if not isinstance(tokens.get("refresh_token"), str) or not tokens["refresh_token"]:
        raise ValueError("No refresh token is available; complete the authorization flow first.")
    fields = {"client_id": client["client_id"], "refresh_token": tokens["refresh_token"], "grant_type": "refresh_token"}
    if client.get("client_secret"):
        fields["client_secret"] = client["client_secret"]
    return fields


def normalize_tokens(response, existing=None, client_id=None, now=None):
    if client_id and (existing or {}).get("client_id") not in {None, client_id}:
        raise ValueError("The existing tokens belong to a different OAuth client.")
    if not isinstance(response, dict) or not isinstance(response.get("access_token"), str) or not response["access_token"]:
        raise ValueError("The token response did not contain an access token.")
    if str(response.get("token_type", "")).lower() != "bearer":
        raise ValueError("The token response did not specify Bearer authentication.")
    expires = response.get("expires_in")
    if isinstance(expires, bool) or not isinstance(expires, (int, float)) or not math.isfinite(expires) or expires <= 0:
        raise ValueError("The token response did not contain a positive lifetime.")
    now = time.time() if now is None else now
    tokens = {"access_token": response["access_token"], "token_type": "Bearer", "expires_at_unix": now + expires}
    for field in ("refresh_token", "scope"):
        value = response.get(field) or (existing or {}).get(field)
        if isinstance(value, str) and value:
            tokens[field] = value
    if client_id:
        tokens["client_id"] = client_id
    return tokens


def file_input_script(kind):
    return """() => {
  let input = document.querySelector('input[data-local-preview-payload="KIND"]');
  if (!input) {
    input = document.createElement('input');
    input.type = 'file'; input.accept = 'application/json';
    input.dataset.localPreviewPayload = 'KIND';
    document.body.appendChild(input);
  }
  return {selector: 'input[data-local-preview-payload="KIND"]', ready: true};
}
""".replace("KIND", kind)


TOKEN_REQUEST_SCRIPT = """async () => {
  const input = document.querySelector('input[data-local-preview-payload="oauth-request"]');
  if (!input?.files?.length) throw new Error('Upload the private OAuth request JSON first.');
  const fields = JSON.parse(await input.files[0].text());
  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams(fields), credentials: 'omit'
  });
  const data = await response.json();
  if (!response.ok) return {ok: false, httpStatus: response.status};
  Object.defineProperty(globalThis, '__localPreviewGoogleTokens', {
    value: data, writable: true, configurable: true, enumerable: false
  });
  return {ok: true, httpStatus: response.status, expiresIn: data.expires_in,
          hasRefreshToken: Boolean(data.refresh_token), tokenType: data.token_type};
}
"""


def token_request_artifacts(fields, output):
    output = Path(output)
    payload = write_private(output / "token-request.json", fields)
    setup = write_private(output / "setup-file-input.js", file_input_script("oauth-request"))
    execute = write_private(output / "execute-token-request.js", TOKEN_REQUEST_SCRIPT)
    return {"payloadFile": str(payload), "setupScript": str(setup), "requestScript": str(execute)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("import-client", "authorize", "exchange-payload", "refresh-payload", "store-tokens", "listen"):
        command = sub.add_parser(name)
        command.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    sub.choices["import-client"].add_argument("--download", type=Path, required=True)
    sub.choices["authorize"].add_argument("--redirect-uri", required=True)
    sub.choices["authorize"].add_argument("--session-file", type=Path)
    sub.choices["authorize"].add_argument("--scope", action="append")
    sub.choices["exchange-payload"].add_argument("--session", type=Path, required=True)
    sub.choices["exchange-payload"].add_argument("--callback-file", type=Path, required=True)
    sub.choices["store-tokens"].add_argument("--response-file", type=Path, required=True)
    sub.choices["listen"].add_argument("--port", type=int, default=0)
    sub.choices["listen"].add_argument("--path", default="/oauth/callback")
    sub.choices["listen"].add_argument("--timeout", type=float, default=900)
    sub.choices["listen"].add_argument("--runtime-dir", type=Path)
    args = parser.parse_args()
    client_path = args.state_dir / "client.json"
    if args.command == "listen":
        result = listen(args.state_dir, args.port, args.path, args.timeout, args.runtime_dir)
    elif args.command == "import-client":
        import_client(args.download, client_path)
        result = {"clientFile": str(client_path), "imported": True}
    else:
        client = read_private(client_path)
        if args.command == "authorize":
            session, url = authorization_session(client, args.redirect_uri, args.scope)
            output = args.state_dir / ("authorization-" + uuid.uuid4().hex)
            result = {"sessionFile": str(write_private(args.session_file or output / "session.json", session)),
                      "authorizationUrlFile": str(write_private(output / "authorization-url.txt", url + "\n"))}
        elif args.command == "exchange-payload":
            callback = read_private(args.callback_file, as_json=False).strip()
            fields = exchange_fields(client, read_private(args.session), callback)
            result = token_request_artifacts(fields, args.state_dir / ("exchange-" + uuid.uuid4().hex))
        elif args.command == "refresh-payload":
            fields = refresh_fields(client, read_private(args.state_dir / "tokens.json"))
            result = token_request_artifacts(fields, args.state_dir / ("refresh-" + uuid.uuid4().hex))
        else:
            token_path = args.state_dir / "tokens.json"
            existing = read_private(token_path) if token_path.exists() else None
            tokens = normalize_tokens(read_private(args.response_file), existing, client["client_id"])
            write_private(token_path, tokens)
            result = {"tokenFile": str(token_path), "stored": True, "hasRefreshToken": bool(tokens.get("refresh_token"))}
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError)
              else "Private OAuth input could not be read or validated.", file=sys.stderr)
        raise SystemExit(1)
