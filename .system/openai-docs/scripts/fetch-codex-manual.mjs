#!/usr/bin/env node
import {
  access,
  mkdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { constants as fsConstants } from "node:fs";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";
import { inspect, promisify } from "node:util";

const DEFAULT_MANUAL_URL = "https://developers.openai.com/codex/codex-manual.md";
const DEFAULT_CACHE_DIR_NAME = "openai-docs-cache";
const CACHE_FILE_NAME = "codex-manual.md";
const OUTLINE_FILE_NAME = "codex-manual.outline.md";
const HASH_HEADER = "x-content-sha256";
const USER_AGENT = "codex-openai-docs";
const execFileAsync = promisify(execFile);

class ManualFetchError extends Error {
  constructor(message, options) {
    super(message, options);
    this.name = "ManualFetchError";
  }
}

const sha256 = (value) => createHash("sha256").update(value).digest("hex");

const withTimeout = async (promiseFactory, timeoutMs) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await promiseFactory(controller.signal);
  } finally {
    clearTimeout(timeout);
  }
};

const proxyConfigured = () =>
  process.env.HTTP_PROXY ||
  process.env.HTTPS_PROXY ||
  process.env.http_proxy ||
  process.env.https_proxy;

const responseHeaders = (headers) => ({
  get(name) {
    return headers.get(name.toLowerCase()) ?? null;
  },
});

const makeResponse = ({ body, headers, status }) => ({
  headers: responseHeaders(headers),
  ok: status >= 200 && status < 300,
  status,
  async text() {
    return body;
  },
});

const parseCurlHeaders = (rawHeaders) => {
  const normalized = rawHeaders.replace(/\r\n/g, "\n").trim();
  const blocks = normalized.split(/\n\n+/).filter(Boolean);
  const headerBlock = [...blocks]
    .reverse()
    .find((block) => block.startsWith("HTTP/"));

  if (!headerBlock) {
    throw new ManualFetchError("curl did not return HTTP response headers.");
  }

  const [statusLine, ...lines] = headerBlock.split("\n");
  const statusMatch = /^HTTP\/\S+\s+(\d{3})/.exec(statusLine);
  if (!statusMatch) {
    throw new ManualFetchError(
      `Could not parse HTTP status from curl response: ${statusLine}`
    );
  }

  const headers = new Map();
  lines.forEach((line) => {
    const separator = line.indexOf(":");
    if (separator === -1) return;
    const name = line.slice(0, separator).trim().toLowerCase();
    const value = line.slice(separator + 1).trim();
    headers.set(name, value);
  });

  return {
    headers,
    status: Number(statusMatch[1]),
  };
};

const tempFilePath = (cacheDir, suffix) =>
  path.join(
    cacheDir,
    `.fetch-codex-manual-${process.pid}-${Date.now()}-${Math.random()
      .toString(16)
      .slice(2)}${suffix}`
  );

const requestManualWithCurl = async (url, { cacheDir, method, timeoutMs }) => {
  const headerPath = tempFilePath(cacheDir, ".headers");
  const bodyPath = tempFilePath(cacheDir, ".body");
  const curlNames =
    process.platform === "win32" ? ["curl.exe", "curl"] : ["curl"];
  const args = [
    "--silent",
    "--show-error",
    "--location",
    "--dump-header",
    headerPath,
    "--output",
    bodyPath,
    "--user-agent",
    USER_AGENT,
    "--max-time",
    String(Math.max(1, Math.ceil(timeoutMs / 1000))),
  ];

  if (method === "HEAD") {
    args.push("--head");
  } else {
    args.push("--request", method);
  }
  args.push(url);

  let lastError;
  for (const curlName of curlNames) {
    try {
      await execFileAsync(curlName, args, { windowsHide: true });
      const [rawHeaders, body] = await Promise.all([
        readFile(headerPath, "utf8"),
        readFile(bodyPath, "utf8"),
      ]);
      const { headers, status } = parseCurlHeaders(rawHeaders);
      return makeResponse({ body, headers, status });
    } catch (error) {
      lastError = error;
      if (error?.code !== "ENOENT") break;
    } finally {
      await Promise.all([
        rm(headerPath, { force: true }),
        rm(bodyPath, { force: true }),
      ]);
    }
  }

  if (lastError?.code === "ENOENT") {
    throw new ManualFetchError("curl is unavailable in this environment.", {
      cause: lastError,
    });
  }
  throw new ManualFetchError(`${method} ${url} could not be fetched.`, {
    cause: lastError,
  });
};

const requestManualWithFetch = async (url, { method, timeoutMs }) => {
  if (typeof fetch !== "function") {
    throw new ManualFetchError(
      "Native fetch is unavailable in this Node runtime."
    );
  }

  return withTimeout(
    (signal) =>
      fetch(url, {
        method,
        headers: { "User-Agent": USER_AGENT },
        signal,
      }),
    timeoutMs
  );
};

const requestManual = async (url, { cacheDir, method, timeoutMs }) => {
  const preferCurl = Boolean(proxyConfigured()) || typeof fetch !== "function";
  const transports = preferCurl
    ? [
        () => requestManualWithCurl(url, { cacheDir, method, timeoutMs }),
        () => requestManualWithFetch(url, { method, timeoutMs }),
      ]
    : [
        () => requestManualWithFetch(url, { method, timeoutMs }),
        () => requestManualWithCurl(url, { cacheDir, method, timeoutMs }),
      ];

  let lastError;
  for (const transport of transports) {
    try {
      const response = await transport();
      if (!response.ok) {
        throw new ManualFetchError(
          `${method} ${url} failed with HTTP ${response.status}.`
        );
      }
      return response;
    } catch (error) {
      lastError = error;
    }
  }

  throw new ManualFetchError(`${method} ${url} could not be fetched.`, {
    cause: lastError,
  });
};

const readHeaderSha = (response) => {
  const value = response.headers.get(HASH_HEADER);
  if (!value || !/^[a-f0-9]{64}$/i.test(value)) {
    throw new ManualFetchError(`Manual response is missing ${HASH_HEADER}.`);
  }
  return value.toLowerCase();
};

const nearestExistingParent = async (target) => {
  let current = target;
  while (true) {
    try {
      const info = await stat(current);
      return info.isDirectory() ? current : null;
    } catch (error) {
      if (error?.code !== "ENOENT") return null;
    }

    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
};

const usableCacheDir = async (cacheDir) => {
  if (!cacheDir) return null;
  const resolved = path.resolve(cacheDir);

  try {
    const info = await stat(resolved);
    if (!info.isDirectory()) return null;
  } catch (error) {
    if (error?.code !== "ENOENT") return null;
  }

  const parent = await nearestExistingParent(resolved);
  if (!parent) return null;

  try {
    await access(parent, fsConstants.W_OK | fsConstants.X_OK);
  } catch {
    return null;
  }

  return resolved;
};

const defaultCacheDirCandidates = () => {
  const candidates = [];
  const seen = new Set();
  const pushCandidate = (candidate) => {
    if (!candidate || seen.has(candidate)) return;
    seen.add(candidate);
    candidates.push(candidate);
  };

  [process.env.TMPDIR, process.env.TEMP, process.env.TMP].forEach((baseDir) => {
    if (baseDir) {
      pushCandidate(path.join(baseDir, DEFAULT_CACHE_DIR_NAME));
    }
  });

  if (process.platform !== "win32") {
    pushCandidate(`/private/tmp/${DEFAULT_CACHE_DIR_NAME}`);
    pushCandidate(`/tmp/${DEFAULT_CACHE_DIR_NAME}`);
  }

  return candidates;
};

const resolveCacheDir = async (cacheDir) => {
  if (cacheDir) {
    return usableCacheDir(cacheDir);
  }

  for (const candidate of defaultCacheDirCandidates()) {
    const usable = await usableCacheDir(candidate);
    if (usable) return usable;
  }

  return null;
};
