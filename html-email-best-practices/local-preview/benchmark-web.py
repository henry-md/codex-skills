#!/usr/bin/env python3
"""Measure saved HTML through fresh, verified Gmail or Outlook inspection evidence."""

import argparse
import base64
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import gmail
import preview

BASE = Path(__file__).resolve().parent
PAYLOAD_LABEL = "Local preview Gmail benchmark payload"


class BenchmarkError(Exception):
    pass


def cli(session, arguments, output=None):
    """Keep browser URLs and raw diagnostic output out of benchmark logs."""
    command = ["chrome-devtools", *map(str, arguments), "--sessionId", session]
    if output:
        output = Path(output)
        output.unlink(missing_ok=True)
        command += ["--filePath", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode or re.search(r"^Error:|^Uncaught", result.stdout, re.M):
        raise BenchmarkError("DevTools step failed: " + str(arguments[0]))
    if output and not output.is_file():
        raise BenchmarkError("DevTools did not return the requested evidence file.")
    return result.stdout


def evaluate(session, page, source, output=None, function=False):
    return cli(session, ["evaluate_script", "--sourcePath", source, "--format",
                        "function" if function else "script", "--pageId", page,
                        "--waitForStableDom", "false"], output)


def read_result(path):
    result = json.loads(Path(path).read_text())
    if not isinstance(result, dict):
        raise BenchmarkError("The browser returned an unexpected result shape.")
    return result


def find_payload_uid(snapshot):
    matches = re.findall(r'uid=(\S+)[^\n]*"' + re.escape(PAYLOAD_LABEL) + r'"', snapshot)
    if len(matches) != 1:
        raise BenchmarkError("The named Gmail payload input was not unique in the current snapshot.")
    return matches[0]


def find_outlook_page(listing, subject=None):
    matches = []
    for line in listing.splitlines():
        if subject:
            match = re.match(r"^(\d+): " + re.escape(subject) + r" -", line)
        else:
            match = re.match(r"^(\d+): Mail - .+ \(https://outlook\.live\.com/mail/\)", line)
        if match:
            matches.append(int(match.group(1)))
    if len(matches) > 1:
        raise BenchmarkError("More than one matching native Outlook window was found.")
    return matches[0] if matches else None


def verify_inspection(result, trial, expected_images):
    if not result.get("ok") or not result.get("readiness", {}).get("ready"):
        raise BenchmarkError("The native message identity or readiness check failed.")
    if any(result.get("truncated", {}).values()):
        raise BenchmarkError("The native inspection was truncated.")
    if result.get("sourceSHA256") != trial["sourceSHA256"]:
        raise BenchmarkError("The inspection's source provenance differs from this revision.")
    check = result.get("benchmark", {})
    if check.get("marker") != trial["marker"] or not check.get("markerPresent") or not check.get("endingPresent"):
        raise BenchmarkError("The native message does not contain this revision's marker and ending.")
    images = result.get("readiness", {}).get("images", {})
    if images.get("total") != expected_images or images.get("pending") or images.get("broken"):
        raise BenchmarkError("The expected message images were not all loaded.")
    return images


def inspect_request(client, trial, manifest, gmail_id, ending, timeout_ms):
    options = {"expectedSubject": manifest["message"]["subject"],
               "sourceSHA256": trial["sourceSHA256"], "expectedEnding": ending,
               "timeoutMs": timeout_ms}
    function = "inspectOpenedOutlook"
    if client == "gmail-web":
        function = "inspectInsertedGmail"
        options["gmailMessageId"] = gmail_id
    # Recheck the current native root after the client-specific identity guard.
    return """async () => {
  const result = await FUNCTION(OPTIONS);
  if (!result.ok) return result;
  const body = document.querySelector(result.rootSelector);
  const text = body ? (body.innerText || body.textContent || '') : '';
  return {...result, benchmark: {
    marker: MARKER, markerPresent: text.includes(MARKER), endingPresent: text.includes(ENDING),
    userAgent: navigator.userAgent, viewport: {width: innerWidth, height: innerHeight},
    devicePixelRatio, artifactCoverage: 'full message DOM, within inspector limits'
  }};
}
""".replace("FUNCTION", function).replace("OPTIONS", json.dumps(options)).replace("MARKER", json.dumps(trial["marker"])).replace("ENDING", json.dumps(ending))


def run_trial(args, benchmark, trial, previous):
    root = Path(benchmark["root"]) / "local" / args.client / ("revision-" + str(trial["trial"]))
    attempt = len(previous) + 1
    folder = root / ("attempt-" + str(attempt))
    preview.private_directory(folder)
    source = Path(trial["referenceFile"]).read_bytes()
    if hashlib.sha256(source).hexdigest() != trial["sourceSHA256"]:
        raise BenchmarkError("The shared revision reference changed before this trial.")
    started_epoch = time.time()
    started = time.perf_counter()
    first_epoch = previous[0]["startedEpochSeconds"] if previous else started_epoch
    result = {"trial": trial["trial"], "attempt": attempt, "client": args.client,
              "marker": trial["marker"], "sourceSHA256": trial["sourceSHA256"],
              "startedAt": datetime.fromtimestamp(started_epoch, timezone.utc).isoformat(),
              "startedEpochSeconds": started_epoch, "stagesSeconds": {},
              "boundary": "Immediately before saving revised HTML through returned, verified native DOM evidence.",
              "warmSetupExcluded": "Browser authentication, API authorization and installed helper code."}
    run_dir = None
    stage = "save"

    def checkpoint(name):
        result["stagesSeconds"][name] = round(time.perf_counter() - started, 3)

    try:
        # This is the first per-revision mutation, after the end-to-end timer starts.
        revised = folder / "email.html"
        preview.atomic_bytes(revised, source)
        checkpoint("htmlSaved")
        stage = "prepare"
        run_dir, manifest = preview.prepare(revised, [args.client], state_dir=folder)
        if manifest["source"]["sha256"] != trial["sourceSHA256"] or manifest["assets"]["issues"]:
            raise BenchmarkError("Prepared source or asset references do not match the benchmark revision.")
        preview.record(run_dir, args.client, "started")
        gmail_id = None
        page = args.mail_page
        if args.client == "gmail-web":
            artifacts = gmail.prepare(run_dir)
            setup = Path(artifacts["setupScript"])
            setup.write_text(setup.read_text().replace("  return {selector:",
                             "  input.setAttribute('aria-label', " + json.dumps(PAYLOAD_LABEL) + ");\n  return {selector:"))
            checkpoint("requestPrepared")
            stage = "gmail-upload"
            evaluate(args.session_id, args.api_page, setup, function=True)
            snapshot = cli(args.session_id, ["take_snapshot", args.api_page])
            uid = find_payload_uid(snapshot)
            cli(args.session_id, ["upload_file", args.api_page, uid, artifacts["payloadFile"]])
            checkpoint("payloadUploaded")
            stage = "gmail-insert"
            result["insertMayHaveSucceeded"] = True
            insert_path = run_dir / "gmail-insert-response.json"
            evaluate(args.session_id, args.api_page, artifacts["requestScript"], insert_path, function=True)
            inserted = read_result(insert_path)
            if not inserted.get("ok") or not re.fullmatch(r"[a-f\d]{1,64}", inserted.get("messageId", ""), re.I):
                raise BenchmarkError("Gmail did not confirm insertion; do not retry an ambiguous POST automatically.")
            gmail_id = inserted["messageId"]
            result["gmailMessageId"] = gmail_id
            checkpoint("insertConfirmed")
            stage = "gmail-navigation"
            cli(args.session_id, ["navigate_page", page, "--url",
                                  "https://mail.google.com/mail/u/0/#all/" + gmail_id, "--timeout", "20000"])
        else:
            stage = "outlook-dispatch"
            listing = cli(args.session_id, ["list_pages"])
            page = find_outlook_page(listing)
            if page is None:
                raise BenchmarkError("No unique signed-in native Outlook.com inbox was found.")
            evaluate(args.session_id, page, BASE / "outlook-preview.js")
            request = run_dir / "outlook-open-request.js"
            options = {"mimeBase64": base64.b64encode((run_dir / "message.eml").read_bytes()).decode(),
                       "expectedSubject": manifest["message"]["subject"], "sourceSHA256": trial["sourceSHA256"],
                       "expectedMessageId": manifest["message"]["messageId"], "expectedRunId": manifest["runId"]}
            preview.atomic_bytes(request, ("() => openOutlookEML(" + json.dumps(options) + ")").encode())
            checkpoint("requestPrepared")
            dispatched_path = run_dir / "outlook-dispatch.json"
            evaluate(args.session_id, page, request, dispatched_path, function=True)
            if not read_result(dispatched_path).get("ok"):
                raise BenchmarkError("Outlook refused the prepared MIME file.")
            checkpoint("fileDispatched")
            stage = "outlook-viewer"
            deadline = time.perf_counter() + args.timeout_ms / 1000
            page = None
            while page is None and time.perf_counter() < deadline:
                page = find_outlook_page(cli(args.session_id, ["list_pages"]), manifest["message"]["subject"])
            if page is None:
                raise BenchmarkError("The expected native reading popup did not appear.")
        checkpoint("nativePageOpened")
        result["pageId"] = page
        stage = "inspect"
        evaluate(args.session_id, page, BASE / "browser-inspect.js")
        evaluate(args.session_id, page, BASE / ("gmail-inspect.js" if args.client == "gmail-web" else "outlook-preview.js"))
        request = run_dir / "inspect-request.js"
        preview.atomic_bytes(request, inspect_request(args.client, trial, manifest, gmail_id, args.ending, args.timeout_ms).encode())
        inspection = run_dir / "native-inspection.json"
        evaluate(args.session_id, page, request, inspection, function=True)
        observed = read_result(inspection)
        result["images"] = verify_inspection(observed, trial, args.expected_images)
        checkpoint("domReturnedAndChecked")
        preview.record(run_dir, args.client, "ready", observed_message_id=manifest["message"]["messageId"],
                       observed_source_hash=trial["sourceSHA256"], inspection=inspection)
        if not preview.validate(run_dir, [args.client])["valid"]:
            raise BenchmarkError("Fresh native inspection evidence failed validation.")
        result.update({"ok": True, "feedbackSeconds": round(time.perf_counter() - started, 3),
                       "cumulativeFeedbackSeconds": round(time.time() - first_epoch, 3),
                       "inspectionFile": str(inspection), "runDir": str(run_dir),
                       "nativeIdentity": observed.get("nativeIdentity"), "configuration": observed["benchmark"]})
        if args.screenshot:
            stage = "screenshot"
            screenshot = run_dir / "native-viewport.png"
            cli(args.session_id, ["take_screenshot", page, "--format", "png", "--fullPage", "false"], screenshot)
            preview.image_extension(screenshot.read_bytes())
            result.update({"screenshotFile": str(screenshot), "screenshotCoverage": "browser viewport, not a full-message image",
                           "screenshotSeconds": round(time.perf_counter() - started, 3)})
    except Exception as error:
        # Never include raw CLI output, authorization URLs or credential values.
        message = str(error) if isinstance(error, BenchmarkError) else "Benchmark step failed: " + type(error).__name__
        if result.get("ok") and stage == "screenshot":
            result["screenshotError"] = message
        else:
            result.update({"ok": False, "error": message, "failedStage": stage,
                           "elapsedSeconds": round(time.perf_counter() - started, 3),
                           "cumulativeElapsedSeconds": round(time.time() - first_epoch, 3)})
            if run_dir is not None:
                preview.record(run_dir, args.client, "error", error=message)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--client", required=True, choices=["gmail-web", "outlook-web"])
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--mail-page", type=int, required=True)
    parser.add_argument("--api-page", type=int)
    parser.add_argument("--trial", type=int)
    parser.add_argument("--ending", default="Update Email Preference")
    parser.add_argument("--expected-images", type=int, default=6)
    parser.add_argument("--timeout-ms", type=int, default=20000)
    parser.add_argument("--screenshot", action="store_true")
    args = parser.parse_args()
    if args.client == "gmail-web" and args.api_page is None:
        parser.error("Gmail requires the already authorized clean --api-page.")
    if not 100 <= args.timeout_ms <= 60000 or args.expected_images < 0:
        parser.error("Use timeout 100–60000 ms and a nonnegative image count.")
    benchmark = json.loads(args.benchmark.read_text())
    destination = Path(benchmark["root"]) / "local" / args.client / "results.json"
    results = json.loads(destination.read_text()) if destination.exists() else []
    for trial in benchmark["trials"]:
        if args.trial is not None and args.trial != trial["trial"]:
            continue
        previous = [entry for entry in results if entry["trial"] == trial["trial"]]
        if any(entry.get("ok") for entry in previous):
            continue
        result = run_trial(args, benchmark, trial, previous)
        results.append(result)
        preview.atomic_json(destination, results)
        print(json.dumps({key: result[key] for key in ("trial", "attempt", "client", "ok", "feedbackSeconds",
              "cumulativeFeedbackSeconds", "screenshotSeconds", "elapsedSeconds", "error", "failedStage") if key in result}), flush=True)
        if not result["ok"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
