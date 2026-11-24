#!/usr/bin/env python3
"""Prepare native email previews and track evidence for their exact HTML source."""

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / '.state'
CLIENTS = ('gmail-web', 'outlook-web', 'apple-mail')


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def timestamp(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, timezone.utc).isoformat()


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def atomic_bytes(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2) + '\n').encode())


@contextmanager
def manifest_lock(run_dir):
    descriptor = os.open(Path(run_dir) / '.manifest.lock', os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, 'r+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def parse_clients(value):
    clients = list(dict.fromkeys(part.strip() for part in value.split(',') if part.strip()))
    if not clients or any(client not in CLIENTS for client in clients):
        raise ValueError('Choose gmail-web, outlook-web, or apple-mail.')
    return clients


class AssetScanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references = set()
        self.in_style = False

    def css(self, text):
        for match in re.finditer(r'url\(\s*[\'"]?([^\)\'"\s]+)', text, re.I):
            self.references.add(match.group(1))
        for match in re.finditer(r'@import\s+[\'"]([^\'"]+)', text, re.I):
            self.references.add(match.group(1))

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        self.in_style = self.in_style or tag == 'style'
        for key in ('src', 'background', 'poster'):
            if attrs.get(key):
                self.references.add(attrs[key])
        if tag == 'link' and attrs.get('href'):
            self.references.add(attrs['href'])
        if attrs.get('srcset'):
            remaining = attrs['srcset']
            while remaining.strip(' ,\t\r\n'):
                remaining = remaining.lstrip(' ,\t\r\n')
                token = re.match(r'\S+', remaining).group()
                self.references.add(token.rstrip(','))
                remaining = remaining[len(token):]
                if not token.endswith(','):
                    remaining = remaining.partition(',')[2]
        self.css(attrs.get('style', ''))

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.css(data)


def asset_report(html):
    scanner = AssetScanner()
    scanner.feed(html)
    hosted, local, issues = [], [], []
    embedded = 0
    for value in sorted(scanner.references):
        scheme = urlsplit(value).scheme.lower()
        if scheme in {'https', 'http'}:
            hosted.append(value)
            if scheme == 'http':
                issues.append({'code': 'insecure-asset-url', 'url': value})
        elif scheme == 'data':
            embedded += 1
        elif scheme == 'cid':
            issues.append({'code': 'attachment-not-provided', 'url': value})
        elif value.startswith('#'):
            continue
        elif not scheme or scheme == 'file':
            local.append(value)
            issues.append({'code': 'local-or-relative-asset', 'url': value})
        else:
            issues.append({'code': 'unsupported-asset-scheme', 'url': value})
    return {'hostedUrls': hosted, 'localPaths': local, 'embeddedAssetCount': embedded, 'issues': issues}


def make_message(source, run_id, source_hash, sender, recipient, created):
    message = EmailMessage(policy=policy.SMTP)
    message_id = f'<local-preview.{run_id}@preview.invalid>'
    subject = f'[LocalPreview {run_id}]'
    message['From'] = sender
    message['To'] = recipient
    message['Date'] = format_datetime(datetime.fromtimestamp(created, timezone.utc))
    message['Subject'] = subject
    message['Message-ID'] = message_id
    message['X-Source-Hash'] = source_hash
    message['X-LocalPreview-Run-ID'] = run_id
    message['MIME-Version'] = '1.0'
    message['Content-Type'] = 'text/html; charset="utf-8"'
    message['Content-Transfer-Encoding'] = 'base64'
    # Encoding the original bytes directly preserves even their original final newline.
    message.set_payload(base64.encodebytes(source).decode('ascii'))
    return message.as_bytes(), {'messageId': message_id, 'subject': subject, 'sourceHashHeader': 'X-Source-Hash'}


def prepare(html_path, clients, state_dir=DEFAULT_STATE, sender='Local Preview <local-preview@preview.invalid>', recipient='preview@preview.invalid'):
    clients = parse_clients(','.join(clients))
    html_path = Path(html_path).expanduser().resolve(strict=True)
    source = html_path.read_bytes()
    html = source.decode('utf-8')
    created = time.time()
    run_id = datetime.fromtimestamp(created, timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:10]
    state_dir = Path(state_dir).expanduser().resolve()
    private_directory(state_dir)
    private_directory(state_dir / 'runs')
    run_dir = state_dir / 'runs' / run_id
    private_directory(run_dir)
    source_hash = sha256(source)
    eml, identity = make_message(source, run_id, source_hash, sender, recipient, created)
    atomic_bytes(run_dir / 'source.html', source)
    atomic_bytes(run_dir / 'message.eml', eml)
    manifest = {
        'schemaVersion': 1, 'runId': run_id, 'createdAt': timestamp(created), 'createdEpochSeconds': created,
        'source': {'path': str(html_path), 'sha256': source_hash, 'bytes': len(source)},
        'message': identity,
        'files': {'html': str(run_dir / 'source.html'), 'eml': str(run_dir / 'message.eml'), 'emlSha256': sha256(eml)},
        'assets': asset_report(html), 'clients': {client: {'status': 'pending'} for client in clients},
    }
    atomic_json(run_dir / 'manifest.json', manifest)
    return run_dir, manifest


def load_manifest(run_dir):
    run_dir = Path(run_dir).expanduser().resolve(strict=True)
    manifest = json.loads((run_dir / 'manifest.json').read_text())
    if manifest.get('schemaVersion') != 1:
        raise ValueError('Unsupported local preview manifest version.')
    return run_dir, manifest


def source_errors(manifest):
    errors = []
    expected = manifest['source']['sha256']
    for code, path in [('current-source', manifest['source']['path']), ('frozen-source', manifest['files']['html'])]:
        try:
            if sha256(Path(path).read_bytes()) != expected:
                errors.append(code + '-changed')
        except OSError:
            errors.append(code + '-missing')
    try:
        eml = Path(manifest['files']['eml']).read_bytes()
        parsed = BytesParser(policy=policy.default).parsebytes(eml)
        if sha256(eml) != manifest['files']['emlSha256']:
            errors.append('mime-file-changed')
        if parsed.get_content_type() != 'text/html' or sha256(parsed.get_payload(decode=True) or b'') != expected:
            errors.append('mime-html-does-not-match-source')
        if str(parsed.get('Message-ID', '')) != manifest['message']['messageId'] or str(parsed.get('X-Source-Hash', '')) != expected:
            errors.append('mime-identity-does-not-match-source')
    except (OSError, ValueError, TypeError):
        errors.append('mime-file-unreadable')
    return errors


def image_extension(content):
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if content.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        return '.webp'
    raise ValueError('The screenshot must be a PNG, JPEG, or WebP image.')


def inspection_epoch(item, expected_hash):
    try:
        text = item['content'].decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('Inspection evidence must be UTF-8 DOM or accessibility inspection data.') from None
    if not text.strip():
        raise ValueError('Inspection evidence must contain DOM or accessibility inspection data.')
    observed = item['modified']
    if item['sourcePath'].suffix.lower() != '.json':
        return observed
    structured = json.loads(text)
    if not isinstance(structured, (dict, list)) or not structured:
        raise ValueError('JSON inspection evidence must contain an object or array.')
    if not isinstance(structured, dict):
        return observed
    if structured.get('ok') is False:
        raise ValueError('The inspection reported that it failed.')
    readiness = structured.get('readiness')
    if isinstance(readiness, dict) and readiness.get('requested') is True and readiness.get('ready') is False:
        raise ValueError('The inspection reported that the requested readiness check failed.')
    inspected_hash = structured.get('sourceSHA256', structured.get('sourceSha256'))
    if inspected_hash is not None and inspected_hash != expected_hash:
        raise ValueError('The inspection source hash does not match this run.')
    if 'capturedAt' in structured:
        try:
            captured = datetime.fromisoformat(structured['capturedAt'].replace('Z', '+00:00'))
            if captured.tzinfo is None:
                raise ValueError('A capture timestamp needs a timezone.')
            # Copying a saved inspector result must not make its capture fresh.
            observed = min(observed, captured.timestamp())
        except (AttributeError, TypeError, ValueError, OverflowError):
            raise ValueError('The inspection capturedAt must be an ISO timestamp with a timezone.') from None
    return observed


def record(run_dir, client, status, screenshot=None, observed_message_id=None, observed_source_hash=None, evidence=(), error=None, inspection=None):
    with manifest_lock(run_dir):
        return record_unlocked(run_dir, client, status, screenshot, observed_message_id, observed_source_hash, evidence, error, inspection)


def record_unlocked(run_dir, client, status, screenshot, observed_message_id, observed_source_hash, evidence, error, inspection):
    run_dir, manifest = load_manifest(run_dir)
    if status not in {'started', 'ready', 'error'}:
        raise ValueError('Choose started, ready, or error for the client status.')
    if client not in manifest['clients']:
        raise ValueError('This client was not selected for the run.')
    now = time.time()
    previous = manifest['clients'][client]
    if status == 'started':
        entry = {'status': 'started', 'startedAt': timestamp(now), 'startedEpochSeconds': now}
    elif status == 'error':
        if not error:
            raise ValueError('An error status needs a short error description.')
        entry = {**previous, 'status': 'error', 'recordedAt': timestamp(now), 'error': error}
    else:
        errors = source_errors(manifest)
        if errors:
            raise ValueError('The run source is stale: ' + ', '.join(errors))
        if observed_message_id != manifest['message']['messageId'] or observed_source_hash != manifest['source']['sha256']:
            raise ValueError('The observed native message identity does not match this run.')
        started = previous.get('startedEpochSeconds', manifest['createdEpochSeconds'])
        inputs = []
        paths = ([inspection] if inspection else []) + list(evidence)
        for path in dict.fromkeys(Path(path).expanduser().resolve(strict=True) for path in paths):
            value = path.read_bytes()
            inputs.append({'sourcePath': path, 'content': value, 'modified': path.stat().st_mtime})
        primary = inputs[0] if inspection else None
        if not screenshot and not primary:
            primary = next((item for item in inputs if item['modified'] >= started), None)
        if primary:
            if primary['modified'] < started:
                raise ValueError('The inspection evidence predates this client run.')
            primary['observed'] = inspection_epoch(primary, manifest['source']['sha256'])
            if primary['observed'] < started:
                raise ValueError('The inspection evidence predates this client run.')
        if not screenshot and not primary:
            if inputs:
                raise ValueError('No inspection evidence is fresh for this client run.')
            raise ValueError('A ready client needs fresh DOM/AX inspection evidence or a native screenshot.')
        image = None
        if screenshot:
            screenshot = Path(screenshot).expanduser().resolve(strict=True)
            captured = screenshot.stat().st_mtime
            if captured < started:
                raise ValueError('The screenshot predates this client run.')
            content = screenshot.read_bytes()
            image = {'content': content, 'extension': image_extension(content), 'captured': captured}
        client_dir = run_dir / 'clients' / client
        private_directory(client_dir)
        evidence_files = []
        inspection_file = None
        for index, item in enumerate(inputs):
            target = client_dir / f'evidence-{index + 1}{item["sourcePath"].suffix}'
            atomic_bytes(target, item['content'])
            saved = {'path': str(target), 'sha256': sha256(item['content']),
                     'observedEpochSeconds': item.get('observed', item['modified'])}
            evidence_files.append(saved)
            if item is primary:
                inspection_file = saved
        entry = {key: previous[key] for key in ('startedAt', 'startedEpochSeconds') if key in previous}
        entry.update({'status': 'ready', 'recordedAt': timestamp(now),
                 'observedMessageId': observed_message_id, 'observedSourceHash': observed_source_hash,
                 'evidence': evidence_files})
        readiness = []
        if inspection_file:
            inspected = primary['observed']
            entry.update({'inspection': inspection_file, 'inspectedAt': timestamp(inspected),
                          'inspectedEpochSeconds': inspected, 'inspectionElapsedSeconds': round(inspected - started, 3)})
            readiness.append(inspected)
        if image:
            destination = client_dir / ('screenshot' + image['extension'])
            atomic_bytes(destination, image['content'])
            captured = image['captured']
            entry.update({'screenshot': {'path': str(destination), 'sha256': sha256(image['content'])},
                          'capturedAt': timestamp(captured), 'capturedEpochSeconds': captured,
                          'captureElapsedSeconds': round(captured - started, 3)})
            readiness.append(captured)
        ready_at = min(readiness)
        entry.update({'readyAt': timestamp(ready_at), 'readyEpochSeconds': ready_at,
                      'elapsedSeconds': round(ready_at - started, 3)})
    manifest['clients'][client] = entry
    atomic_json(run_dir / 'manifest.json', manifest)
    return manifest


def validate(run_dir, clients=None):
    run_dir, manifest = load_manifest(run_dir)
    selected = clients or list(manifest['clients'])
    errors = [{'code': code} for code in source_errors(manifest)]
    for client in selected:
        entry = manifest['clients'].get(client)
        if not entry or entry.get('status') != 'ready':
            errors.append({'client': client, 'code': 'client-not-ready'})
            continue
        if entry.get('observedSourceHash') != manifest['source']['sha256'] or entry.get('observedMessageId') != manifest['message']['messageId']:
            errors.append({'client': client, 'code': 'native-message-identity-mismatch'})
        screenshot = entry.get('screenshot')
        inspection = entry.get('inspection')
        if not screenshot and not inspection:
            errors.append({'client': client, 'code': 'readiness-evidence-missing'})
        started = entry.get('startedEpochSeconds', manifest['createdEpochSeconds'])
        if inspection and entry.get('inspectedEpochSeconds', 0) < started:
            errors.append({'client': client, 'code': 'inspection-evidence-stale'})
        if screenshot and entry.get('capturedEpochSeconds', 0) < started:
            errors.append({'client': client, 'code': 'screenshot-stale'})
        for evidence in ([screenshot] if screenshot else []) + ([inspection] if inspection else []) + entry.get('evidence', []):
            try:
                if sha256(Path(evidence['path']).read_bytes()) != evidence['sha256']:
                    errors.append({'client': client, 'code': 'evidence-changed'})
            except OSError:
                errors.append({'client': client, 'code': 'evidence-missing'})
    return {'runId': manifest['runId'], 'sourceSha256': manifest['source']['sha256'],
            'valid': not errors, 'clients': selected, 'errors': errors}


def export(run_dir, destination, clients=None):
    checked = validate(run_dir, clients)
    if not checked['valid']:
        raise ValueError('Export refused because the selected native evidence is stale or incomplete: ' + json.dumps(checked['errors']))
    run_dir, manifest = load_manifest(run_dir)
    without_images = [client for client in checked['clients'] if not manifest['clients'][client].get('screenshot')]
    if without_images:
        raise ValueError('Image export requires a screenshot for: ' + ', '.join(without_images))
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    for client in checked['clients']:
        source = Path(manifest['clients'][client]['screenshot']['path'])
        target = destination / (client + source.suffix)
        atomic_bytes(target, source.read_bytes(), mode=0o644)
        files.append(str(target))
    result = {**checked, 'files': files, 'exportedAt': timestamp()}
    atomic_json(run_dir / 'export.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--html', type=Path, required=True)
    prepare_parser.add_argument('--clients', type=parse_clients, default=list(CLIENTS))
    prepare_parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE)
    prepare_parser.add_argument('--sender', default='Local Preview <local-preview@preview.invalid>')
    prepare_parser.add_argument('--recipient', default='preview@preview.invalid')
    record_parser = commands.add_parser('record')
    record_parser.add_argument('--run-dir', type=Path, required=True)
    record_parser.add_argument('--client', choices=CLIENTS, required=True)
    record_parser.add_argument('--status', choices=('started', 'ready', 'error'), default='ready')
    record_parser.add_argument('--screenshot', type=Path)
    record_parser.add_argument('--inspection', type=Path, help='Fresh DOM or accessibility inspection evidence; a screenshot is optional.')
    record_parser.add_argument('--observed-message-id')
    record_parser.add_argument('--observed-source-hash')
    record_parser.add_argument('--evidence', type=Path, action='append', default=[])
    record_parser.add_argument('--error')
    for name in ('validate', 'export'):
        command = commands.add_parser(name)
        command.add_argument('--run-dir', type=Path, required=True)
        command.add_argument('--clients', type=parse_clients)
        if name == 'export':
            command.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        run_dir, manifest = prepare(args.html, args.clients, args.state_dir, args.sender, args.recipient)
        print(json.dumps({'runId': manifest['runId'], 'runDir': str(run_dir), 'manifest': str(run_dir / 'manifest.json'),
                          'sourceSha256': manifest['source']['sha256'], 'messageId': manifest['message']['messageId'],
                          'subject': manifest['message']['subject'], 'assetIssues': len(manifest['assets']['issues'])}))
    elif args.command == 'record':
        manifest = record(args.run_dir, args.client, args.status, args.screenshot, args.observed_message_id,
                          args.observed_source_hash, args.evidence, args.error, args.inspection)
        print(json.dumps({'runId': manifest['runId'], 'client': args.client, **manifest['clients'][args.client]}))
    else:
        result = validate(args.run_dir, args.clients) if args.command == 'validate' else export(args.run_dir, args.destination, args.clients)
        print(json.dumps(result))
        if not result['valid']:
            raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
