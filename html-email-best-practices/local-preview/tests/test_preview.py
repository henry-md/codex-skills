import base64
import concurrent.futures
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_preview', ROOT / 'preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9s8AAAAASUVORK5CYII=')


class PreviewTests(unittest.TestCase):
    def fixture(self, root, source=b'<html><body>Current email</body></html>', clients=('gmail-web',)):
        html = root / 'email.html'
        html.write_bytes(source)
        return preview.prepare(html, clients, root / 'state')

    def screenshot(self, root, name='native.png'):
        image = root / name
        image.write_bytes(PNG)
        return image

    def ready(self, run_dir, manifest, image, client='gmail-web'):
        return preview.record(run_dir, client, 'ready', image,
                              manifest['message']['messageId'], manifest['source']['sha256'])

    def test_utf8_mime_roundtrip_preserves_exact_html_bytes(self):
        sources = [
            '<html><body>Résumé • 日本語 😀</body></html>'.encode(),
            b'<html>\r\n<body>Windows line endings</body>\r\n</html>\r\n',
            b'<html><body>No trailing newline</body></html>',
        ]
        for source in sources:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary:
                run_dir, manifest = self.fixture(Path(temporary), source)
                message = BytesParser(policy=policy.default).parsebytes((run_dir / 'message.eml').read_bytes())
                self.assertEqual(message.get_content_type(), 'text/html')
                self.assertEqual(message.get_content_charset(), 'utf-8')
                self.assertEqual(message.get_payload(decode=True), source)
                self.assertEqual(str(message['Message-ID']), manifest['message']['messageId'])
                self.assertEqual(str(message['X-Source-Hash']).strip(), preview.sha256(source))
                self.assertEqual(preview.source_errors(manifest), [])

    def test_run_and_message_identity_are_unique(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, first = self.fixture(root)
            _, second = self.fixture(root)
            self.assertNotEqual(first['runId'], second['runId'])
            self.assertNotEqual(first['message']['messageId'], second['message']['messageId'])
            self.assertNotEqual(first['message']['subject'], second['message']['subject'])
            self.assertEqual(first['source']['sha256'], second['source']['sha256'])

    def test_changed_source_refuses_export_without_touching_existing_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            self.ready(run_dir, manifest, self.screenshot(root))
            destination = root / 'export'
            destination.mkdir()
            existing = destination / 'gmail-web.png'
            existing.write_bytes(b'previous capture')
            (root / 'email.html').write_text('<html>Edited after capture</html>')
            self.assertFalse(preview.validate(run_dir)['valid'])
            with self.assertRaisesRegex(ValueError, 'stale or incomplete'):
                preview.export(run_dir, destination)
            self.assertEqual(existing.read_bytes(), b'previous capture')

    def test_old_screenshot_and_wrong_message_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            image = self.screenshot(root)
            old = manifest['createdEpochSeconds'] - 60
            os.utime(image, (old, old))
            with self.assertRaisesRegex(ValueError, 'predates'):
                self.ready(run_dir, manifest, image)
            image.write_bytes(PNG)
            with self.assertRaisesRegex(ValueError, 'identity'):
                preview.record(run_dir, 'gmail-web', 'ready', image, '<wrong@preview.invalid>', manifest['source']['sha256'])

    def test_recorded_evidence_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            recorded = self.ready(run_dir, manifest, self.screenshot(root))
            self.assertTrue(preview.validate(run_dir)['valid'])
            Path(recorded['clients']['gmail-web']['screenshot']['path']).write_bytes(b'changed image')
            result = preview.validate(run_dir)
            self.assertFalse(result['valid'])
            self.assertIn('evidence-changed', [entry['code'] for entry in result['errors']])

    def test_mime_tampering_is_detected_even_when_html_stays_the_same(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            path = run_dir / 'message.eml'
            content = path.read_bytes().replace(b'local-preview.', b'other-preview.', 1)
            path.write_bytes(content)
            self.assertIn('mime-file-changed', preview.source_errors(manifest))
            self.assertIn('mime-identity-does-not-match-source', preview.source_errors(manifest))

    def test_partial_export_only_copies_selected_ready_client(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root, clients=('gmail-web', 'apple-mail'))
            self.ready(run_dir, manifest, self.screenshot(root))
            self.assertFalse(preview.validate(run_dir)['valid'])
            exported = preview.export(run_dir, root / 'export', ['gmail-web'])
            self.assertEqual([Path(path).name for path in exported['files']], ['gmail-web.png'])
            self.assertEqual(list((root / 'export').iterdir()), [root / 'export' / 'gmail-web.png'])
            self.assertTrue(preview.validate(run_dir, ['gmail-web'])['valid'])

    def test_assets_report_hosted_local_cid_and_embedded_references(self):
        html = '''<html><head><style>.hero{background:url("https://cdn.example/hero.jpg")}</style></head><body>
            <img src="./logo.png"><img src="cid:missing"><img src="data:image/png;base64,AAAA">
            <img srcset="data:image/png;base64,AAAA 1x, https://cdn.example/retina.png 2x">
            <a href="https://example.com">Not an asset</a></body></html>'''
        report = preview.asset_report(html)
        self.assertEqual(report['hostedUrls'], ['https://cdn.example/hero.jpg', 'https://cdn.example/retina.png'])
        self.assertEqual(report['localPaths'], ['./logo.png'])
        self.assertEqual(report['embeddedAssetCount'], 1)
        self.assertIn('attachment-not-provided', [issue['code'] for issue in report['issues']])

    def test_concurrent_client_updates_keep_both_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root, clients=('gmail-web', 'apple-mail'))
            images = {client: self.screenshot(root, client + '.png') for client in ('gmail-web', 'apple-mail')}
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.ready, run_dir, manifest, image, client) for client, image in images.items()]
                for future in futures:
                    future.result()
            result = preview.validate(run_dir)
            self.assertTrue(result['valid'], result)

    def test_atomic_json_readers_never_see_partial_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'manifest.json'
            preview.atomic_json(path, {'sequence': 0, 'payload': 'x' * 10000})
            stopped = threading.Event()
            failures = []
            def read():
                while not stopped.is_set():
                    try:
                        self.assertEqual(len(json.loads(path.read_text())['payload']), 10000)
                    except Exception as error:
                        failures.append(error)
                        return
            reader = threading.Thread(target=read)
            reader.start()
            try:
                for number in range(30):
                    preview.atomic_json(path, {'sequence': number, 'payload': 'x' * 10000})
            finally:
                stopped.set()
                reader.join()
            self.assertEqual(failures, [])

    def test_private_state_permissions_and_credential_ignore(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, _ = self.fixture(Path(temporary))
            self.assertEqual(stat.S_IMODE(run_dir.stat().st_mode), 0o700)
            for name in ('source.html', 'message.eml', 'manifest.json'):
                self.assertEqual(stat.S_IMODE((run_dir / name).stat().st_mode), 0o600)
        result = subprocess.run(['git', 'check-ignore', '--no-index', str(ROOT / '.state' / 'auth' / 'google-client.json')],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_cli_and_gmail_payload_preserve_the_same_native_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = '<html><body>Résumé 日本語 😀</body></html>'.encode()
            html = root / 'email.html'
            html.write_bytes(source)
            prepared = subprocess.run([sys.executable, str(ROOT / 'preview.py'), 'prepare', '--html', str(html),
                                       '--clients', 'gmail-web', '--state-dir', str(root / 'state')],
                                      capture_output=True, text=True, check=True)
            run = json.loads(prepared.stdout)
            generated = subprocess.run([sys.executable, str(ROOT / 'gmail.py'), 'prepare', '--run-dir', run['runDir']],
                                       capture_output=True, text=True, check=True)
            artifacts = json.loads(generated.stdout)
            payload = json.loads(Path(artifacts['payloadFile']).read_text())
            encoded = payload['raw']
            message = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
            self.assertEqual(message.get_payload(decode=True), source)
            self.assertEqual(str(message['Message-ID']), run['messageId'])
            self.assertEqual(payload['labelIds'], ['INBOX', 'UNREAD'])
            self.assertEqual(stat.S_IMODE(Path(artifacts['payloadFile']).stat().st_mode), 0o600)

    def test_dom_only_ready_evidence_validates_without_claiming_image_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            inspection = root / 'inspection.json'
            inspection.write_text(json.dumps({'ok': True, 'sourceSHA256': manifest['source']['sha256'],
                                              'root': {'text': 'Current email'}, 'elements': [{'tag': 'body'}]}))
            recorded = preview.record(run_dir, 'gmail-web', 'ready',
                                      observed_message_id=manifest['message']['messageId'],
                                      observed_source_hash=manifest['source']['sha256'], inspection=inspection)
            entry = recorded['clients']['gmail-web']
            self.assertTrue(preview.validate(run_dir)['valid'])
            self.assertIn('inspection', entry)
            self.assertIn('inspectedAt', entry)
            self.assertNotIn('screenshot', entry)
            self.assertNotIn('capturedAt', entry)
            self.assertEqual(entry['inspectedEpochSeconds'], inspection.stat().st_mtime)
            self.assertEqual(entry['readyEpochSeconds'], inspection.stat().st_mtime)
            self.assertEqual(entry['elapsedSeconds'], entry['inspectionElapsedSeconds'])
            with self.assertRaisesRegex(ValueError, 'Image export requires a screenshot'):
                preview.export(run_dir, root / 'export')
            self.assertFalse((root / 'export').exists())

    def test_ready_without_any_native_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, manifest = self.fixture(Path(temporary))
            with self.assertRaisesRegex(ValueError, 'fresh DOM/AX'):
                preview.record(run_dir, 'gmail-web', 'ready',
                               observed_message_id=manifest['message']['messageId'],
                               observed_source_hash=manifest['source']['sha256'])
            self.assertEqual(preview.load_manifest(run_dir)[1]['clients']['gmail-web']['status'], 'pending')

    def test_stale_ax_evidence_cannot_mark_a_client_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            evidence = root / 'message-ax.txt'
            evidence.write_text('AXWindow: Current email\n  AXStaticText: Footer')
            old = manifest['createdEpochSeconds'] - 60
            os.utime(evidence, (old, old))
            with self.assertRaisesRegex(ValueError, 'predates'):
                preview.record(run_dir, 'gmail-web', 'ready',
                               observed_message_id=manifest['message']['messageId'],
                               observed_source_hash=manifest['source']['sha256'], inspection=evidence)
            with self.assertRaisesRegex(ValueError, 'No inspection evidence is fresh'):
                preview.record(run_dir, 'gmail-web', 'ready',
                               observed_message_id=manifest['message']['messageId'],
                               observed_source_hash=manifest['source']['sha256'], evidence=[evidence])

    def test_fresh_ax_evidence_fallback_and_tampering_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root, clients=('apple-mail',))
            evidence = root / 'message-ax.txt'
            evidence.write_text('AXWindow: Current email\n  AXStaticText: Footer')
            recorded = preview.record(run_dir, 'apple-mail', 'ready',
                                      observed_message_id=manifest['message']['messageId'],
                                      observed_source_hash=manifest['source']['sha256'], evidence=[evidence])
            self.assertTrue(preview.validate(run_dir)['valid'])
            Path(recorded['clients']['apple-mail']['inspection']['path']).write_text('Changed AX snapshot')
            self.assertFalse(preview.validate(run_dir)['valid'])

    def test_failed_or_wrong_source_dom_inspections_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            inspection = root / 'inspection.json'
            for content in ({'ok': False, 'error': 'No unique email body'}, {'ok': True, 'sourceSHA256': '0' * 64}):
                inspection.write_text(json.dumps(content))
                with self.assertRaises(ValueError):
                    preview.record(run_dir, 'gmail-web', 'ready',
                                   observed_message_id=manifest['message']['messageId'],
                                   observed_source_hash=manifest['source']['sha256'], inspection=inspection)

    def test_copying_an_old_inspector_result_does_not_refresh_its_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            inspection = root / 'copied-inspection.json'
            inspection.write_text(json.dumps({'ok': True, 'root': {'tag': 'body'},
                                              'capturedAt': preview.timestamp(manifest['createdEpochSeconds'] - 60)}))
            self.assertGreaterEqual(inspection.stat().st_mtime, manifest['createdEpochSeconds'])
            with self.assertRaisesRegex(ValueError, 'predates'):
                preview.record(run_dir, 'gmail-web', 'ready',
                               observed_message_id=manifest['message']['messageId'],
                               observed_source_hash=manifest['source']['sha256'], inspection=inspection)

    def test_inspector_timestamp_sets_inspection_time_and_failed_readiness_rejects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, manifest = self.fixture(root)
            inspection = root / 'inspection.json'
            captured = time.time()
            content = {'ok': True, 'capturedAt': preview.timestamp(captured), 'root': {'tag': 'body'},
                       'readiness': {'requested': True, 'ready': False}}
            inspection.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, 'readiness check failed'):
                preview.record(run_dir, 'gmail-web', 'ready',
                               observed_message_id=manifest['message']['messageId'],
                               observed_source_hash=manifest['source']['sha256'], inspection=inspection)
            content['readiness']['ready'] = True
            inspection.write_text(json.dumps(content))
            recorded = preview.record(run_dir, 'gmail-web', 'ready',
                                      observed_message_id=manifest['message']['messageId'],
                                      observed_source_hash=manifest['source']['sha256'], inspection=inspection)
            entry = recorded['clients']['gmail-web']
            self.assertAlmostEqual(entry['inspectedEpochSeconds'], captured, places=5)
            self.assertEqual(entry['inspection']['observedEpochSeconds'], entry['inspectedEpochSeconds'])
            self.assertTrue(preview.validate(run_dir)['valid'])


if __name__ == '__main__':
    unittest.main()
