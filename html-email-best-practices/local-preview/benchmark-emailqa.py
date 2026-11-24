#!/usr/bin/env python3
"""Measure saved HTML through a verified, downloaded EmailQA screenshot."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit
from urllib.request import urlopen
import uuid

CLIENTS = ('gmail-web', 'outlook-web', 'apple-mail')


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def safe_error(error):
    text = re.sub(r'https?://[^\s]+', '[redacted URL]', str(error))
    return text[:400]


def public_job(job):
    # Keep signed image URLs in memory only.
    names = ('id', 'status', 'cached', 'completedCount', 'totalCount', 'createdAt', 'completedAt')
    result = {name: job[name] for name in names if name in job}
    result['results'] = [
        {name: row[name] for name in ('client', 'status', 'error', 'width', 'height') if name in row}
        for row in job.get('results', [])
    ]
    return result


def download_image(url, destination):
    if urlsplit(url).scheme != 'https':
        raise RuntimeError('The provider image URL was not HTTPS.')
    with urlopen(url, timeout=45) as response:
        if urlsplit(response.url).scheme != 'https':
            raise RuntimeError('The provider redirected its image to an insecure URL.')
        content = response.read(30 * 1024 * 1024 + 1)
    if len(content) > 30 * 1024 * 1024 or not content.startswith(b'\x89PNG\r\n\x1a\n'):
        raise RuntimeError('The screenshot was oversized or not a PNG.')
    destination.write_bytes(content)
    destination.chmod(0o600)
    return {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}


# A trial includes every per-revision step after the new source file starts saving.
def measure_trial(api, key, project, trial, client, folder, verifier, timeout_seconds):
    wanted = client if client == 'gmail-web' else client + '-light'
    output = {'client': client, 'targetResult': wanted, 'trial': trial['trial'],
              'sourceSHA256': trial['sourceSHA256'], 'marker': trial['marker'],
              'configuration': {'catalogId': client, 'mode': 'light', 'platform': 'Mac',
                                'providerVersions': 'not exposed by catalog'},
              'attempts': [], 'stages': {}, 'ok': False}
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    result_path = folder / 'result.json'
    source_path = folder / 'email.html'
    image_path = folder / (wanted + '.png')
    job = None
    started = time.perf_counter()
    output['startedAt'] = timestamp()

    def elapsed():
        return round(time.perf_counter() - started, 6)

    def stage(name):
        output['stages'][name] = {'at': timestamp(), 'elapsedSeconds': elapsed()}
        write_json(result_path, output)

    try:
        html_bytes = Path(trial['referenceFile']).read_bytes()
        source_path.write_bytes(html_bytes)
        source_path.chmod(0o600)
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != trial['sourceSHA256']:
            raise RuntimeError('Saved source hash differs from the canonical benchmark revision.')
        html = html_bytes.decode('utf-8')
        if trial['marker'] not in html:
            raise RuntimeError('The canonical HTML does not contain the revision marker.')
        stage('sourceSavedAndVerified')
        version_response = api.request_api(key, 'POST', f'/api/v1/projects/{quote(project)}/versions', {'html': html})
        version = version_response['data']['versionNumber']
        output['project'] = project
        output['version'] = version
        stage('versionUploaded')
        idempotency = 'codex-e2e-' + uuid.uuid4().hex
        output['idempotencyKey'] = idempotency
        job = api.request_api(key, 'POST', f'/api/v1/projects/{quote(project)}/renders',
                              {'version': version, 'clients': [client], 'test': False},
                              idempotency_key=idempotency)['data']
        output['jobId'] = job['id']
        output['cached'] = job.get('cached', False)
        stage('renderSubmitted')
        deadline = started + timeout_seconds
        next_progress = time.perf_counter() + 20
        while True:
            observation = {'observedAt': timestamp(), 'elapsedSeconds': elapsed(), **public_job(job)}
            output['attempts'].append(observation)
            for row in job.get('results', []):
                if output['ok'] or row.get('client') != wanted or row.get('status') != 'success':
                    continue
                stage('targetAPIReady')
                try:
                    output['image'] = {'path': str(image_path), **download_image(row['screenshotUrl'], image_path)}
                    stage('imageDownloaded')
                    checked = subprocess.run([str(verifier), str(image_path), trial['marker'], 'Update Email Preference'],
                                             capture_output=True, text=True, timeout=60)
                    if checked.returncode > 1:
                        raise RuntimeError('The offline PNG verifier failed: ' + checked.stderr[:200])
                    verification = json.loads(checked.stdout)
                    output['verification'] = verification
                    if not verification.get('decodedPNG') or not verification.get('markerFound') or not verification.get('endingFound'):
                        raise RuntimeError('The screenshot did not pass image decoding, current marker and ending checks.')
                    stage('imageDecodedAndFreshnessVerified')
                    output['ok'] = True
                    output['endToEndSeconds'] = elapsed()
                    output['readyAt'] = timestamp()
                    print(json.dumps({'event': 'image_ready', 'client': client, 'trial': trial['trial'],
                                      'endToEndSeconds': output['endToEndSeconds'], 'cached': output['cached']}), flush=True)
                except Exception as error:
                    output.setdefault('retrievalFailures', []).append({'at': timestamp(), 'elapsedSeconds': elapsed(), 'error': safe_error(error)})
                    if 'verification' in output:
                        raise
            write_json(result_path, output)
            terminal = job['status'] not in ('queued', 'processing')
            if terminal:
                output['terminalJob'] = public_job(job)
                output['terminalAtSeconds'] = elapsed()
                if not output['ok']:
                    raise RuntimeError('The job ended without a verified current target screenshot.')
                break
            if time.perf_counter() >= deadline:
                raise RuntimeError('The render exceeded the benchmark timeout; do not resubmit this job automatically.')
            if time.perf_counter() >= next_progress:
                print(json.dumps({'event': 'pending', 'client': client, 'trial': trial['trial'],
                                  'seconds': elapsed(), 'targetReady': output['ok'], 'jobStatus': job['status']}), flush=True)
                next_progress = time.perf_counter() + 20
            time.sleep(1)
            job = api.request_api(key, 'GET', '/api/v1/renders/' + quote(job['id']))['data']
    except Exception as error:
        output['error'] = {'type': type(error).__name__, 'message': safe_error(error), 'elapsedSeconds': elapsed()}
        output['jobStillActive'] = bool(job and job.get('status') in ('queued', 'processing'))
        print(json.dumps({'event': 'trial_error', 'client': client, 'trial': trial['trial'], **output['error']}), flush=True)
    output['recordedAt'] = timestamp()
    write_json(result_path, output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--integration', type=Path, default=Path('/Users/Henry/.codex/integrations/emailqa/render.py'))
    parser.add_argument('--verifier', type=Path, required=True)
    parser.add_argument('--clients', default=','.join(CLIENTS))
    parser.add_argument('--timeout-seconds', type=int, default=600)
    args = parser.parse_args()
    clients = args.clients.split(',')
    if not clients or any(client not in CLIENTS for client in clients) or len(set(clients)) != len(clients):
        parser.error('Select unique supported client IDs.')
    manifest = json.loads(args.benchmark.read_text())
    if len(manifest['trials']) != 3:
        parser.error('This benchmark expects three marked canonical revisions.')
    root = Path(manifest['root']) / 'emailqa'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    spec = importlib.util.spec_from_file_location('emailqa_integration', args.integration)
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    key = api.load_key()
    usage = api.request_api(key, 'GET', '/api/v1/usage')['data']
    catalog = api.request_api(key, 'GET', '/api/v1/clients')['data']
    available = {row['id']: row for row in catalog if row.get('status') == 'available'}
    # Conservatively budget both light/dark outputs where the catalog requires them.
    needed = 3 * sum(2 if available.get(client, {}).get('darkMode') else 1 for client in clients)
    if usage['monthlyPreviews']['remaining'] < needed or usage['rateLimits']['activeJobs']:
        raise RuntimeError('Insufficient included allowance or another EmailQA job is active.')
    if any(client not in available for client in clients):
        raise RuntimeError('A required analogous provider client is unavailable.')
    summary = {'benchmarkId': manifest['benchmarkId'], 'provider': 'EmailQA', 'project': args.project,
               'apiPlan': usage['apiPlan'], 'usageBefore': usage['monthlyPreviews'],
               'catalog': [available[c] for c in clients], 'timingBoundary': manifest['timingBoundary'],
               'endpoint': 'Downloaded and decoded PNG with OCR-matched current revision marker and complete ending',
               'startedAt': timestamp(), 'trials': []}
    write_json(root / 'summary.json', summary)
    for client in clients:
        for trial in manifest['trials']:
            result = measure_trial(api, key, args.project, trial, client,
                                   root / client / f'trial-{trial["trial"]}', args.verifier, args.timeout_seconds)
            summary['trials'].append(result)
            write_json(root / 'summary.json', summary)
            if result.get('jobStillActive'):
                return 2
        print(json.dumps({'event': 'client_complete', 'client': client,
                          'seconds': [r.get('endToEndSeconds') for r in summary['trials'] if r['client'] == client],
                          'allPassed': all(r['ok'] for r in summary['trials'] if r['client'] == client)}), flush=True)
    summary['usageAfter'] = api.request_api(key, 'GET', '/api/v1/usage')['data']['monthlyPreviews']
    summary['finishedAt'] = timestamp()
    write_json(root / 'summary.json', summary)
    return 0 if all(row['ok'] for row in summary['trials']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
