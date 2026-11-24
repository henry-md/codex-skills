import http.client
import json
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import oauth


CLIENT = {"client_id": "fixture.apps.googleusercontent.com", "client_secret": "fixture-client-secret"}
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"


class OAuthTests(unittest.TestCase):
    def setUp(self):
        state = ROOT / ".state"
        state.mkdir(exist_ok=True, mode=0o700)
        self.temporary = tempfile.TemporaryDirectory(dir=state)
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def session(self):
        return oauth.authorization_session(CLIENT, "http://127.0.0.1:8765/callback", now=100,
                                           verifier=VERIFIER, state="fixture-state")

    def test_pkce_matches_rfc_vector_without_sending_verifier_or_secret(self):
        session, url = self.session()
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["code_challenge"], ["E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["scope"], [oauth.INSERT_SCOPE])
        self.assertNotIn(VERIFIER, url)
        self.assertNotIn(CLIENT["client_secret"], url)
        self.assertEqual(session["codeVerifier"], VERIFIER)

    def test_callback_requires_same_state_redirect_and_unexpired_session(self):
        session, _ = self.session()
        callback = "http://127.0.0.1:8765/callback?state=fixture-state&code=fixture-code"
        fields = oauth.exchange_fields(CLIENT, session, callback, now=101)
        self.assertEqual(fields["grant_type"], "authorization_code")
        self.assertEqual(fields["code_verifier"], VERIFIER)
        self.assertEqual(fields["code"], "fixture-code")
        for invalid in (callback.replace("fixture-state", "wrong-state"), callback.replace(":8765", ":8766"), callback + "&code=second"):
            with self.assertRaises(ValueError):
                oauth.exchange_fields(CLIENT, session, invalid, now=101)
        with self.assertRaisesRegex(ValueError, "expired"):
            oauth.exchange_fields(CLIENT, session, callback, now=1001)

    def test_unsupported_redirects_and_broader_scopes_are_rejected(self):
        for uri in ("urn:ietf:wg:oauth:2.0:oob", "https://example.test/callback", "http://127.0.0.1:8765/callback?code=private"):
            with self.assertRaises(ValueError):
                oauth.authorization_session(CLIENT, uri)
        with self.assertRaises(ValueError):
            oauth.authorization_session(CLIENT, "http://127.0.0.1:8765", ["https://mail.google.com/"])

    def test_refresh_keeps_existing_refresh_token_when_google_omits_it(self):
        existing = {"refresh_token": "fixture-refresh", "scope": oauth.INSERT_SCOPE}
        tokens = oauth.normalize_tokens({"access_token": "fixture-new-access", "expires_in": 3600, "token_type": "Bearer"}, existing, now=100)
        self.assertEqual(tokens["refresh_token"], "fixture-refresh")
        self.assertEqual(tokens["expires_at_unix"], 3700)
        fields = oauth.refresh_fields(CLIENT, tokens)
        self.assertEqual(fields["refresh_token"], "fixture-refresh")
        self.assertEqual(fields["grant_type"], "refresh_token")

    def test_import_makes_download_and_saved_client_owner_only(self):
        download = self.root / "download.json"
        download.write_text(json.dumps({"installed": {**CLIENT, "auth_uri": oauth.AUTH_URI, "token_uri": oauth.TOKEN_URI}}))
        download.chmod(0o644)
        target = self.root / "oauth" / "client.json"
        oauth.import_client(download, target)
        self.assertEqual(download.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(oauth.read_private(target)["client_id"], CLIENT["client_id"])

    def test_official_desktop_download_shape_normalizes_legacy_auth_endpoint(self):
        download = self.root / "desktop-client.json"
        download.write_text(json.dumps({"installed": {
            **CLIENT, "project_id": "fixture-project", "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": oauth.TOKEN_URI,
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        }}))
        target = self.root / "imported" / "client.json"
        normalized = oauth.import_client(download, target)
        self.assertEqual(normalized["auth_uri"], oauth.AUTH_URI)
        self.assertEqual(normalized["token_uri"], oauth.TOKEN_URI)
        self.assertEqual(oauth.read_private(target), normalized)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_client_import_rejects_unrecognized_auth_and_token_endpoints(self):
        download = self.root / "desktop-client.json"
        target = self.root / "imported" / "client.json"
        for endpoints in ({"auth_uri": "https://accounts.google.com.attacker.test/o/oauth2/auth"},
                          {"auth_uri": "http://accounts.google.com/o/oauth2/auth"},
                          {"auth_uri": "https://accounts.google.com/o/oauth2/auth?redirect=elsewhere"},
                          {"token_uri": "https://attacker.test/token"},
                          {"token_uri": "https://accounts.google.com/o/oauth2/token"}):
            download.write_text(json.dumps({"installed": {**CLIENT, **endpoints}}))
            with self.assertRaisesRegex(ValueError, "expected Google authorization endpoints"):
                oauth.import_client(download, target)
            self.assertFalse(target.exists())

    def test_request_scripts_and_cli_output_never_embed_credentials(self):
        session, _ = self.session()
        fields = oauth.exchange_fields(CLIENT, session, "http://127.0.0.1:8765/callback?state=fixture-state&code=fixture-code", now=101)
        result = oauth.token_request_artifacts(fields, self.root / "request")
        public = json.dumps(result) + Path(result["requestScript"]).read_text() + Path(result["setupScript"]).read_text()
        for private in (CLIENT["client_secret"], VERIFIER, "fixture-code"):
            self.assertNotIn(private, public)
        for artifact in result.values():
            self.assertEqual(Path(artifact).stat().st_mode & 0o777, 0o600)

    def test_private_input_rejects_group_readable_tokens(self):
        path = self.root / "tokens.json"
        path.write_text('{"refresh_token":"fixture-refresh"}')
        path.chmod(0o640)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            oauth.read_private(path)

    def test_token_storage_does_not_mix_clients_or_accept_invalid_lifetimes(self):
        response = {"access_token": "fixture-access", "expires_in": 3600, "token_type": "Bearer"}
        with self.assertRaisesRegex(ValueError, "different OAuth client"):
            oauth.normalize_tokens(response, {"client_id": "other-client", "refresh_token": "other-refresh"}, CLIENT["client_id"])
        for lifetime in (float("nan"), float("inf"), 0, True):
            with self.assertRaisesRegex(ValueError, "positive lifetime"):
                oauth.normalize_tokens({**response, "expires_in": lifetime})

    def test_default_runtime_state_is_covered_by_skill_ignore(self):
        rules = (ROOT / ".gitignore").read_text().splitlines()
        self.assertIn(".state/", rules)
        self.assertEqual(oauth.DEFAULT_STATE, ROOT / ".state" / "oauth")

    def start_listener(self, timeout=3):
        process = subprocess.Popen([sys.executable, str(ROOT / "oauth.py"), "listen", "--state-dir", str(self.root),
                                    "--timeout", str(timeout)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=3)
        self.addCleanup(cleanup)
        self.assertTrue(select.select([process.stdout], [], [], 3)[0], "Listener did not publish its ready info.")
        line = process.stdout.readline()
        self.assertTrue(line, "Listener exited before publishing ready info.")
        return process, json.loads(line), line

    def local_get(self, info, target):
        address = urlsplit(info["redirectUri"])
        connection = http.client.HTTPConnection("127.0.0.1", address.port, timeout=2)
        try:
            connection.request("GET", target)
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()

    def test_loopback_captures_only_valid_callback_and_keeps_secrets_out_of_output(self):
        oauth.write_private(self.root / "client.json", CLIENT)
        process, info, initial_output = self.start_listener()
        authorized = subprocess.run([sys.executable, str(ROOT / "oauth.py"), "authorize", "--state-dir", str(self.root),
                                     "--redirect-uri", info["redirectUri"], "--session-file", info["sessionFile"]],
                                    text=True, capture_output=True, check=True)
        session = oauth.read_private(info["sessionFile"])
        path = urlsplit(info["redirectUri"]).path
        for target in ("/wrong-path?code=private-code", path, path + "?state=wrong&code=private-code",
                       path + "?state=" + session["state"]):
            status, _ = self.local_get(info, target)
            self.assertIn(status, (400, 404))
            self.assertFalse(Path(info["callbackFile"]).exists())
        query = path + "?state=" + session["state"] + "&code=private-code"
        status, response = self.local_get(info, query)
        self.assertEqual(status, 200)
        output, errors = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, errors)
        callback = oauth.read_private(info["callbackFile"], as_json=False)
        self.assertEqual(oauth.exchange_fields(CLIENT, session, callback)["code"], "private-code")
        self.assertEqual(oauth.read_private(info["readyFile"])["status"], "captured")
        for private in ("private-code", session["state"], session["codeVerifier"], CLIENT["client_secret"]):
            self.assertNotIn(private, initial_output + output + errors + response + authorized.stdout + authorized.stderr)
        self.assertEqual(Path(info["readyFile"]).parent.stat().st_mode & 0o777, 0o700)
        for file in (info["callbackFile"], info["readyFile"], info["sessionFile"]):
            self.assertEqual(Path(file).stat().st_mode & 0o777, 0o600)

    def test_loopback_times_out_without_callback_and_closes_port(self):
        process, info, _ = self.start_listener(timeout=0.1)
        output, errors = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 1)
        self.assertIn("timed out", errors)
        self.assertFalse(Path(info["callbackFile"]).exists())
        self.assertEqual(oauth.read_private(info["readyFile"])["status"], "timed-out")
        with self.assertRaises(OSError):
            self.local_get(info, "/oauth/callback")

    def test_loopback_saves_matching_provider_decline_without_claiming_success(self):
        process, info, _ = self.start_listener()
        session, _ = oauth.authorization_session(CLIENT, info["redirectUri"])
        oauth.write_private(info["sessionFile"], session)
        path = urlsplit(info["redirectUri"]).path
        status, response = self.local_get(info, path + "?state=" + session["state"] + "&error=access_denied")
        self.assertEqual(status, 200)
        output, errors = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, errors)
        self.assertEqual(json.loads(output)["status"], "declined")
        self.assertNotIn("access_denied", output + errors + response)
        with self.assertRaisesRegex(ValueError, "declined"):
            oauth.exchange_fields(CLIENT, session, oauth.read_private(info["callbackFile"], as_json=False))


if __name__ == "__main__":
    unittest.main()
