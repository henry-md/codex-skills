#!/usr/bin/env python3
"""Evaluate Jev questions from JSON or resumable JSONL; Python standard library only."""
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import random
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.13.0"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a credential to a destination chosen by an HTTP redirect.
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def number(value, low=0, high=1):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and low <= value <= high)


def identity(value):
    require(isinstance(value, (str, int)) and not isinstance(value, bool)
            and value != "", "id must be a nonempty string or integer")
    return json.dumps(value, ensure_ascii=False)


def request_from(row, batch):
    require(isinstance(row, dict), "input record must be an object")
    require(not batch or "id" in row, "each JSONL record requires an id")
    item_id = row.get("id", "single")
    identity(item_id)
    state = row.get("state")
    require(isinstance(state, (str, dict, list)), "state must be text, object, or array")
    model = row.get("model", DEFAULT_MODEL)
    require(isinstance(model, str) and bool(model.strip()), "model must be a nonempty string")
    questions = row.get("questions")
    require(isinstance(questions, dict) and bool(questions), "questions must be a nonempty object")
    for name, question in questions.items():
        require(isinstance(name, str) and bool(name), "question ids must be nonempty strings")
        require(isinstance(question, dict), "question must be an object")
        kind = question.get("type")
        require(kind in ("choice", "noul", "score"), "unsupported question type")
        require(isinstance(question.get("instructions"), (str, dict, list)),
                "instructions must be text, object, or array")
        criteria = question.get("criteria")
        if kind == "choice":
            require(isinstance(criteria, dict) and 2 <= len(criteria) <= 255,
                    "choice requires 2 to 255 named criteria")
            require(all(isinstance(k, str) and k for k in criteria), "invalid choice label")
        elif kind == "score":
            require(isinstance(criteria, list) and 2 <= len(criteria) <= 10,
                    "score requires 2 to 10 ordered criteria")
        elif criteria is not None:
            require(isinstance(criteria, dict) and set(criteria) <= {"true", "false"},
                    "noul criteria must contain only true/false descriptions")
    payload = {"state": state, "model": model, "questions": questions}
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError):
        raise Invalid("request contains invalid JSON values") from None
    return {"id": item_id, "payload": payload, "body": encoded,
            "request_hash": hashlib.sha256(encoded).hexdigest()}


def validate_response(body, questions):
    require(isinstance(body, dict), "invalid response")
    require(isinstance(body.get("model"), str) and body["model"], "invalid response model")
    answers = body.get("answers")
    require(isinstance(answers, dict) and set(answers) == set(questions), "invalid answer ids")
    for name, question in questions.items():
        answer = answers[name]
        kind = question["type"]
        require(isinstance(answer, dict) and answer.get("type") == kind, "invalid answer type")
        if kind == "noul":
            require(number(answer.get("noul")), "invalid noul probability")
            continue
        require(number(answer.get("confidence")), "invalid confidence")
        expected = set(question["criteria"]) if kind == "choice" else {
            str(i) for i in range(len(question["criteria"]))}
        probabilities = answer.get("probabilities")
        require(isinstance(probabilities, dict) and set(probabilities) == expected,
                "invalid probability labels")
        require(all(number(p) for p in probabilities.values()), "invalid probability")
        require(abs(sum(probabilities.values()) - 1) <= 0.01, "invalid probability sum")
        if kind == "choice":
            require(isinstance(answer.get("choice"), str) and answer["choice"] in expected,
                    "invalid selected choice")
            require(probabilities[answer["choice"]] + 0.01 >= max(probabilities.values()),
                    "choice disagrees with probabilities")
        else:
            require(number(answer.get("score"), 0, len(expected) - 1), "invalid score")
            legend = answer.get("legend")
            require(isinstance(legend, dict) and set(legend) == expected, "invalid score legend")
            require(all(legend[str(i)] == item for i, item in enumerate(question["criteria"])),
                    "score legend differs from request")
    usage = body.get("usage")
    require(isinstance(usage, dict), "missing token usage")
    require(all(isinstance(usage.get(k), int) and not isinstance(usage[k], bool)
                and usage[k] >= 0 for k in ("input_tokens", "output_tokens")), "invalid token usage")
    return {"model": body["model"], "answers": answers,
            "usage": {k: usage[k] for k in ("input_tokens", "output_tokens")}}


def load_key():
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        try:
            data = json.loads((Path.home() / ".config/jev/credentials.json").read_text())
            key = data.get("TYPESAFE_API_KEY") or data.get("api_key")
        except (OSError, ValueError, AttributeError):
            raise Invalid("credentials unavailable; set TYPESAFE_API_KEY") from None
    require(isinstance(key, str) and bool(key.strip()) and "\n" not in key and "\r" not in key,
            "credentials unavailable; set TYPESAFE_API_KEY")
    return key.strip()


class Pacer:
    def __init__(self, rpm):
        self.interval = 60 / rpm
        self.next_at = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            at = max(now, self.next_at)
            self.next_at = at + self.interval
        time.sleep(max(0, at - time.monotonic()))


def retry_delay(attempt, headers=None):
    delay = 0.8 * 2 ** attempt + random.uniform(0, 0.2)
    if headers:
        value = headers.get("Retry-After")
        if value:
            try:
                delay = float(value)
            except ValueError:
                try:
                    when = parsedate_to_datetime(value)
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                    delay = (when - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    pass
    return min(10, max(0, delay))


def evaluate(record, key, pacer):
    started = time.monotonic()
    result = {"id": record["id"], "request_hash": record["request_hash"],
              "model": record["payload"]["model"]}
    error = "request_failed"
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(3):
        pacer.wait()
        request = urllib.request.Request(ENDPOINT, data=record["body"], method="POST",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with opener.open(request, timeout=45) as response:
                body = json.loads(response.read())
            result.update(validate_response(body, record["payload"]["questions"]))
            result["status"] = "ok"
            break
        except urllib.error.HTTPError as exc:
            error = "http_" + str(exc.code)
            retry = exc.code == 429 or 500 <= exc.code < 600
            delay = retry_delay(attempt, exc.headers)
            exc.close()
            if not retry or attempt == 2:
                break
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
            error = "transport_error"
            delay = retry_delay(attempt)
            if attempt == 2:
                break
        except (ValueError, TypeError, KeyError, UnicodeError):
            error = "invalid_response"
            break
        time.sleep(delay)
    if result.get("status") != "ok":
        result.update(status="error", error=error)
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    return result


def private_output(path, resume):
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if resume else os.O_EXCL)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, "a", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON request or JSONL records")
    parser.add_argument("--output", type=Path, help="private result file (required for JSONL)")
    parser.add_argument("--jsonl", action="store_true", help="input is one {id,state,questions,model?} per line")
    parser.add_argument("--concurrency", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--requests-per-minute", type=int, default=300)
    parser.add_argument("--resume", action="store_true", help="skip successful identical requests in output")
    args = parser.parse_args(argv)
    require(not args.jsonl or args.output is not None, "--jsonl requires --output")
    require(not args.resume or args.output is not None, "--resume requires --output")
    require(1 <= args.requests_per_minute <= 1200, "requests per minute must be between 1 and 1200")
    require(args.output is None or args.input.resolve() != args.output.resolve(),
            "input and output must be different files")
    try:
        content = args.input.read_text(encoding="utf-8")
        rows = [json.loads(line) for line in content.splitlines() if line.strip()] if args.jsonl else [json.loads(content)]
    except (OSError, ValueError):
        raise Invalid("input could not be read as JSON") from None
    records = [request_from(row, args.jsonl) for row in rows]
    ids = [identity(r["id"]) for r in records]
    require(len(set(ids)) == len(ids), "duplicate input ids")
    expected = {identity(r["id"]): r for r in records}
    done = set()
    if args.output and args.output.exists():
        require(args.resume, "output already exists; use --resume or a new output path")
        require(not args.output.is_symlink(), "output must not be a symbolic link")
        try:
            prior = [json.loads(line) for line in args.output.read_text().splitlines() if line.strip()]
        except (OSError, ValueError):
            raise Invalid("checkpoint is invalid JSONL; preserve it and use a new output") from None
        for row in prior:
            require(isinstance(row, dict) and "id" in row, "invalid checkpoint record")
            item_key = identity(row["id"])
            require(item_key in expected and row.get("request_hash") == expected[item_key]["request_hash"],
                    "checkpoint does not match this input and model")
            if row.get("status") == "ok":
                validate_response(row, expected[item_key]["payload"]["questions"])
                done.add(item_key)
    pending = [r for r in records if identity(r["id"]) not in done]
    if not pending:
        print(f"No pending records; {len(done)} already complete.", file=sys.stderr)
        return 0
    key = load_key()
    stream = private_output(args.output, args.resume) if args.output else sys.stdout
    failed = 0
    pacer = Pacer(args.requests_per_minute)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(evaluate, record, key, pacer) for record in pending]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                if args.output:
                    os.fsync(stream.fileno())
                failed += result["status"] != "ok"
    finally:
        if args.output:
            stream.close()
    print(f"Evaluated {len(pending)} records; {failed} errors; {len(done)} resumed.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Invalid as exc:
        print("Error: " + str(exc), file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("Interrupted; completed records are checkpointed.", file=sys.stderr)
        sys.exit(130)
    except Exception:
        print("Error: local operation failed; no request or response content was logged.", file=sys.stderr)
        sys.exit(2)
