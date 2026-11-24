/* Requires browser-inspect.js. These selectors were observed in Gmail's opened-message DOM. */
async function inspectInsertedGmail(options) {
  "use strict";
  const fail = (code, message, extra = {}) => ({ ok: false, error: { code, message }, ...extra });
  if (!options || typeof options !== "object" || Array.isArray(options)) {
    return fail("INVALID_OPTIONS", "Pass the inserted Gmail message ID, expected subject and source SHA-256.");
  }
  const { gmailMessageId, expectedSubject, sourceSHA256 } = options;
  const expectedEnding = options.expectedEnding === undefined ? "Update Email Preference" : options.expectedEnding;
  const timeoutMs = options.timeoutMs === undefined ? 15000 : options.timeoutMs;
  if (typeof gmailMessageId !== "string" || !/^[a-f\d]{1,64}$/i.test(gmailMessageId) ||
      typeof expectedSubject !== "string" || !expectedSubject.trim() || expectedSubject.length > 998 ||
      typeof sourceSHA256 !== "string" || !/^[a-f\d]{64}$/i.test(sourceSHA256) ||
      typeof expectedEnding !== "string" || !expectedEnding.trim() || expectedEnding.length > 1000 ||
      !Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 60000) {
    return fail("INVALID_OPTIONS", "Use a hex Gmail API ID, nonempty subject and ending, SHA-256 hex digest, and timeoutMs from 100 to 60000.");
  }
  if (typeof document === "undefined" || !document.defaultView) {
    return fail("BROWSER_REQUIRED", "Run in the Gmail page containing the opened message.");
  }
  if (typeof inspectEmailDOM !== "function") {
    return fail("INSPECTOR_NOT_LOADED", "Load browser-inspect.js before gmail-inspect.js.");
  }
  const doc = document;
  const win = doc.defaultView;
  const started = win.performance.now();
  const deadline = started + timeoutMs;
  const containerSelector = `.adn.ads[data-legacy-message-id="${gmailMessageId}"]`;
  const rootSelector = `${containerSelector} .a3s.aiL`;
  const normalize = text => text.replace(/\s+/g, " ").trim();
  const subject = expectedSubject.trim();
  const ending = normalize(expectedEnding);
  const visible = element => element.getClientRects().length > 0 &&
    win.getComputedStyle(element).visibility !== "hidden";
  function identify() {
    const headings = Array.from(doc.querySelectorAll("h2.hP")).filter(visible);
    if (headings.length !== 1 || headings[0].textContent.trim() !== subject) {
      return { reason: "subject-not-matched" };
    }
    const containers = doc.querySelectorAll(containerSelector);
    const bodies = doc.querySelectorAll(rootSelector);
    if (containers.length !== 1 || bodies.length !== 1) return { reason: "message-body-not-unique" };
    const body = bodies[0];
    if (!visible(body)) return { reason: "message-body-not-visible" };
    const text = typeof body.innerText === "string" ? body.innerText : body.textContent || "";
    const endingPresent = normalize(text).includes(ending);
    if (!endingPresent) return { reason: "ending-not-found" };
    return { body, heading: headings[0], endingPresent };
  }
  let lastReason = "message-not-found";
  const identity = await new Promise(resolve => {
    let observer;
    let timer;
    let settled = false;
    function finish(value) {
      if (settled) return;
      settled = true;
      if (observer) observer.disconnect();
      if (timer) win.clearTimeout(timer);
      resolve(value);
    }
    function check() {
      const current = identify();
      if (current.body) finish(current);
      else lastReason = current.reason;
    }
    observer = new win.MutationObserver(check);
    observer.observe(doc.documentElement, {
      subtree: true, childList: true, characterData: true, attributes: true,
      attributeFilter: ["class", "data-legacy-message-id", "style", "hidden", "aria-hidden"],
    });
    timer = win.setTimeout(() => finish(null), timeoutMs);
    check();
  });
  const nativeIdentity = { gmailMessageId, subject, endingPresent: !!identity };
  if (!identity) {
    const code = lastReason === "ending-not-found" ? "GMAIL_ENDING_NOT_FOUND" : "GMAIL_MESSAGE_TIMEOUT";
    return fail(code, "The expected Gmail message body, subject and ending did not become ready before the timeout.", {
      nativeIdentity, waitReason: lastReason, elapsedMs: Math.round(win.performance.now() - started),
    });
  }
  const identityReadyMs = Math.round(win.performance.now() - started);
  const remaining = Math.floor(deadline - win.performance.now());
  if (remaining < 100) return fail("GMAIL_MESSAGE_TIMEOUT", "No inspection time remained after identifying the message.", { nativeIdentity });
  let inspected;
  try {
    inspected = await inspectEmailDOM({
      rootSelector, waitForReady: true, sourceSHA256, client: "gmail-web",
      readinessTimeoutMs: Math.min(10000, remaining),
    });
  } catch {
    return fail("INSPECTION_FAILED", "The email DOM could not be inspected; observe the opened message again.", { nativeIdentity });
  }
  const current = identify();
  if (!current.body || current.body !== identity.body || current.heading !== identity.heading) {
    return fail("GMAIL_MESSAGE_CHANGED", "The expected message changed during inspection; open it again before inspecting.", {
      nativeIdentity: { gmailMessageId, subject, endingPresent: !!current.endingPresent },
      waitReason: current.reason || "message-body-replaced",
    });
  }
  return { ...inspected, nativeIdentity: { gmailMessageId, subject, endingPresent: true },
    identityReadyMs, elapsedMs: Math.round(win.performance.now() - started) };
}

if (typeof module !== "undefined" && module.exports) module.exports = { inspectInsertedGmail };
({ inspector: "inspectInsertedGmail" });
