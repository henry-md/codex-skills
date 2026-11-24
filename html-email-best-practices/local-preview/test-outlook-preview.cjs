const { test, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const { webcrypto, createHash } = require("node:crypto");
const { File } = require("node:buffer");
const { openOutlookEML, inspectOpenedOutlook } = require("./outlook-preview.js");

const source = Buffer.from("<p>Current email</p><p>Expected ending</p>");
const hash = createHash("sha256").update(source).digest("hex");
const subject = "[LocalPreview fixture-current]";
const messageId = "<fixture-current@preview.invalid>";
const mime = Buffer.from(`Subject: ${subject}\r\nMessage-ID: ${messageId}\r\nX-Source-Hash: ${hash}\r\nX-LocalPreview-Run-ID: fixture-current\r\nContent-Type: text/html; charset=\"utf-8\"\r\nContent-Transfer-Encoding: base64\r\n\r\n${source.toString("base64")}\r\n`);
const openOptions = { mimeBase64: mime.toString("base64"), expectedSubject: subject, sourceSHA256: hash,
  expectedMessageId: messageId, expectedRunId: "fixture-current" };
const inspectOptions = { expectedSubject: subject, sourceSHA256: hash, expectedEnding: "Expected ending", timeoutMs: 500 };

afterEach(() => { delete global.document; delete global.inspectEmailDOM; });

function browser() {
  const events = [];
  const target = { closest: () => null, dispatchEvent: event => { events.push(event); return true; } };
  const pane = { getClientRects: () => [{}], getBoundingClientRect: () => ({ x: 20, y: 30, width: 600, height: 400 }),
    contains: element => element === target };
  const heading = { textContent: subject, getClientRects: () => [{}] };
  const body = { innerText: "Current email Expected ending", getClientRects: () => [{}] };
  const state = { panes: [pane], headings: [heading], bodies: [body], hitTarget: target, observer: null };
  class Observer {
    constructor(callback) { this.callback = callback; state.observer = this; }
    observe() {}
    disconnect() { this.disconnected = true; }
  }
  class Transfer {
    constructor() { this.files = []; this.items = { add: file => this.files.push(file) }; }
  }
  class Event {
    constructor(type, options) { this.type = type; Object.assign(this, options); }
  }
  const win = { location: { hostname: "outlook.live.com", protocol: "https:" }, innerWidth: 1200, innerHeight: 900,
    TextDecoder, atob, crypto: webcrypto, performance, File, DataTransfer: Transfer, DragEvent: Event,
    getComputedStyle: () => ({ visibility: "visible", display: "block" }), MutationObserver: Observer,
    setTimeout, clearTimeout };
  global.document = { defaultView: win, documentElement: {}, title: subject + " - Private account - Outlook",
    elementFromPoint: (x, y) => { state.hitPoint = { x, y }; return state.hitTarget; },
    querySelectorAll: selector => {
      if (selector === '[aria-label="Reading Pane"][role="main"]') return state.panes;
      if (selector === '[role="heading"].Xz4k3') return state.headings;
      if (selector === 'div[id^="UniqueMessageBody_"][aria-label="Message body"]') return state.bodies;
      throw new Error("Unexpected selector");
    } };
  global.inspectEmailDOM = async () => ({ ok: true, readiness: { ready: true }, images: [], capturedAt: new Date().toISOString() });
  return { state, events, pane, target, heading, body, win };
}

test("requires bounded MIME and explicit run identity before using a browser", async () => {
  for (const options of [undefined, {}, { ...openOptions, mimeBase64: "" }, { ...openOptions, sourceSHA256: "wrong" },
    { ...openOptions, expectedSubject: "" }, { ...openOptions, expectedRunId: {} }]) {
    assert.equal((await openOutlookEML(options)).error.code, "INVALID_OPTIONS");
  }
  assert.equal((await openOutlookEML(openOptions)).error.code, "BROWSER_REQUIRED");
  assert.equal((await inspectOpenedOutlook(inspectOptions)).error.code, "BROWSER_REQUIRED");
  assert.equal((await inspectOpenedOutlook({ ...inspectOptions, expectedEnding: "" })).error.code, "INVALID_OPTIONS");
});

test("dispatches the original MIME bytes on the visible pane's center descendant", async () => {
  const { state, events } = browser();
  const result = await openOutlookEML(openOptions);
  assert.equal(result.ok, true);
  assert.equal(result.renderingVerified, false);
  assert.equal(result.sourceSHA256, hash);
  assert.deepEqual(state.hitPoint, { x: 320, y: 230 });
  assert.deepEqual(events.map(event => event.type), ["dragenter", "dragover", "drop"]);
  assert(events.every(event => event.bubbles && event.cancelable && event.clientX === 320 && event.clientY === 230));
  const transfer = events[2].dataTransfer;
  assert.equal(transfer.effectAllowed, "all");
  assert.equal(transfer.dropEffect, "copy");
  assert.equal(transfer.files[0].name, "message.eml");
  assert.equal(transfer.files[0].type, "message/rfc822");
  assert.deepEqual(Buffer.from(await transfer.files[0].arrayBuffer()), mime);
  assert(!JSON.stringify(result).includes("Private account"));
});

test("does not dispatch an invalid, mismatched or tampered MIME message", async () => {
  const { events } = browser();
  assert.equal((await openOutlookEML({ ...openOptions, mimeBase64: "not base64" })).error.code, "INVALID_MIME");
  assert.equal((await openOutlookEML({ ...openOptions, expectedSubject: "Another run" })).error.code, "MIME_IDENTITY_MISMATCH");
  const tampered = mime.toString().replace(source.toString("base64"), Buffer.from("Different source").toString("base64"));
  assert.equal((await openOutlookEML({ ...openOptions, mimeBase64: Buffer.from(tampered).toString("base64") })).error.code, "MIME_SOURCE_MISMATCH");
  const duplicate = mime.toString().replace("Subject:", "Subject: duplicate\r\nSubject:");
  assert.equal((await openOutlookEML({ ...openOptions, mimeBase64: Buffer.from(duplicate).toString("base64") })).error.code, "INVALID_MIME");
  assert.equal(events.length, 0);
});

test("refuses another origin, ambiguous pane, overlay or editor", async () => {
  const { win, state, events, pane, target } = browser();
  win.location.hostname = "example.com";
  assert.equal((await openOutlookEML(openOptions)).error.code, "WRONG_ORIGIN");
  win.location.hostname = "outlook.live.com";
  state.panes = [pane, pane];
  assert.equal((await openOutlookEML(openOptions)).error.code, "READING_PANE_NOT_UNIQUE");
  state.panes = [pane];
  state.hitTarget = {};
  assert.equal((await openOutlookEML(openOptions)).error.code, "READING_PANE_TARGET_MISSING");
  state.hitTarget = target;
  target.closest = () => ({});
  assert.equal((await openOutlookEML(openOptions)).error.code, "READING_PANE_TARGET_MISSING");
  assert.equal(events.length, 0);
});

test("waits for the visible native body and records only its supplied provenance", async () => {
  const { state, body } = browser();
  state.bodies = [];
  let settled = false;
  const pending = inspectOpenedOutlook(inspectOptions).then(result => { settled = true; return result; });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(settled, false);
  state.bodies = [body];
  state.observer.callback();
  const result = await pending;
  assert.equal(result.ok, true);
  assert.equal(result.readiness.ready, true);
  assert.equal(result.nativeIdentity.loadingMethod, "opened-eml");
  assert.equal(result.nativeIdentity.subject, subject);
  assert.equal(result.nativeIdentity.endingPresent, true);
  assert.match(result.nativeIdentity.sourceHashProvenance, /not extracted/);
  assert.equal(state.observer.disconnected, true);
  assert(!JSON.stringify(result).includes("Private account"));
});

test("rejects a wrong popup title or missing final content", async () => {
  const { body } = browser();
  document.title = "Another message - Private account - Outlook";
  const wrong = await inspectOpenedOutlook({ ...inspectOptions, timeoutMs: 100 });
  assert.equal(wrong.error.code, "OUTLOOK_MESSAGE_TIMEOUT");
  assert.equal(wrong.waitReason, "popup-title-not-matched");
  document.title = subject + " - Private account - Outlook";
  body.innerText = "Current email without final content";
  const incomplete = await inspectOpenedOutlook({ ...inspectOptions, timeoutMs: 100 });
  assert.equal(incomplete.error.code, "OUTLOOK_ENDING_NOT_FOUND");
  assert.equal(incomplete.nativeIdentity.endingPresent, false);
});

test("rejects a body replaced while geometry and assets are being inspected", async () => {
  const { state, body } = browser();
  global.inspectEmailDOM = async () => {
    state.bodies = [{ ...body }];
    return { ok: true, readiness: { ready: true } };
  };
  const changed = await inspectOpenedOutlook(inspectOptions);
  assert.equal(changed.error.code, "OUTLOOK_MESSAGE_CHANGED");
});
