"""Offline checks for full timing boundaries and refusing stale native evidence."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location("benchmark_web", BASE / "benchmark-web.py")
benchmark_web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark_web)


class BenchmarkWebTests(unittest.TestCase):
    def test_matching_current_native_evidence_is_required(self):
        trial = {"marker": "REVISION 2", "sourceSHA256": "a" * 64}
        result = {"ok": True, "sourceSHA256": trial["sourceSHA256"], "truncated": {"html": False},
                  "readiness": {"ready": True, "images": {"total": 6, "pending": 0, "broken": 0}},
                  "benchmark": {"marker": trial["marker"], "markerPresent": True, "endingPresent": True}}
        self.assertEqual(benchmark_web.verify_inspection(result, trial, 6)["total"], 6)
        for field, value in [("markerPresent", False), ("endingPresent", False), ("marker", "REVISION 1")]:
            changed = json.loads(json.dumps(result))
            changed["benchmark"][field] = value
            with self.assertRaises(benchmark_web.BenchmarkError):
                benchmark_web.verify_inspection(changed, trial, 6)
        changed = json.loads(json.dumps(result))
        changed["truncated"]["html"] = True
        with self.assertRaises(benchmark_web.BenchmarkError):
            benchmark_web.verify_inspection(changed, trial, 6)

    def test_native_outlook_discovery_rejects_reply_and_duplicate_windows(self):
        subject = "[LocalPreview trial-2]"
        listing = "1: Mail - Test - Outlook (https://outlook.live.com/mail/)\n2: Re: " + subject + " (about:blank)\n3: " + subject + " - Test - Outlook (about:blank)"
        self.assertEqual(benchmark_web.find_outlook_page(listing), 1)
        self.assertEqual(benchmark_web.find_outlook_page(listing, subject), 3)
        with self.assertRaises(benchmark_web.BenchmarkError):
            benchmark_web.find_outlook_page(listing + "\n4: " + subject + " - Test - Outlook (about:blank)", subject)
        self.assertEqual(benchmark_web.find_payload_uid('uid=5_2 button "' + benchmark_web.PAYLOAD_LABEL + '"'), "5_2")

    def run_gmail(self, root, fail_insert=False, previous=None):
        marker = "REVISION 1"
        source = ("<!doctype html><html><body>" + marker + " ending</body></html>").encode()
        reference = root / "reference.html"
        reference.write_bytes(source)
        trial = {"trial": 1, "marker": marker, "referenceFile": str(reference), "sourceSHA256": hashlib.sha256(source).hexdigest()}
        args = types.SimpleNamespace(client="gmail-web", mail_page=3, api_page=25, session_id="unit-test",
                                     timeout_ms=20000, ending="ending", expected_images=0, screenshot=False)
        clock = [0]
        posts = []
        real_atomic = benchmark_web.preview.atomic_bytes

        def atomic(path, content, mode=0o600):
            if Path(path).name == "email.html":
                clock[0] += 2
            return real_atomic(path, content, mode)

        def cli(session, arguments, output=None):
            clock[0] += 3
            if arguments[0] == "take_snapshot":
                return 'uid=1_0 button "' + benchmark_web.PAYLOAD_LABEL + '"'
            return "ok"

        def evaluate(session, page, source_path, output=None, function=False):
            clock[0] += 5
            name = Path(source_path).name
            if name == "execute-insert.js":
                posts.append(name)
                if fail_insert:
                    raise benchmark_web.BenchmarkError("Ambiguous Gmail insertion")
                Path(output).write_text(json.dumps({"ok": True, "messageId": "abcdef"}))
            elif name == "inspect-request.js":
                Path(output).write_text(json.dumps({"ok": True, "capturedAt": benchmark_web.preview.timestamp(),
                    "sourceSHA256": trial["sourceSHA256"], "truncated": {"html": False},
                    "nativeIdentity": {"gmailMessageId": "abcdef", "endingPresent": True},
                    "readiness": {"requested": True, "ready": True, "images": {"total": 0, "pending": 0, "broken": 0}},
                    "benchmark": {"marker": marker, "markerPresent": True, "endingPresent": True}}))
            return "ok"

        fake_time = types.SimpleNamespace(time=time.time, perf_counter=lambda: clock[0])
        with patch.object(benchmark_web, "time", fake_time), patch.object(benchmark_web, "cli", cli), \
             patch.object(benchmark_web, "evaluate", evaluate), patch.object(benchmark_web.preview, "atomic_bytes", atomic):
            result = benchmark_web.run_trial(args, {"root": str(root)}, trial, previous or [])
        return result, posts, clock[0]

    def test_full_timer_includes_new_file_and_all_browser_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            result, posts, elapsed = self.run_gmail(Path(directory))
            self.assertTrue(result["ok"], result)
            self.assertEqual(posts, ["execute-insert.js"])
            self.assertEqual(result["stagesSeconds"]["htmlSaved"], 2)
            self.assertEqual(result["feedbackSeconds"], elapsed)
            self.assertGreater(elapsed, result["stagesSeconds"]["insertConfirmed"])
            self.assertTrue(Path(result["inspectionFile"]).is_file())

    def test_ambiguous_insert_is_not_retried_and_previous_elapsed_time_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = [{"startedEpochSeconds": time.time() - 30}]
            result, posts, _ = self.run_gmail(Path(directory), fail_insert=True, previous=previous)
            self.assertFalse(result["ok"])
            self.assertEqual(result["failedStage"], "gmail-insert")
            self.assertTrue(result["insertMayHaveSucceeded"])
            self.assertEqual(posts, ["execute-insert.js"])
            self.assertGreaterEqual(result["cumulativeElapsedSeconds"], 30)


if __name__ == "__main__":
    unittest.main()
