/* Browser checks use the real fixture document; Node checks validate the caller contract. */
async function runBrowserInspectionChecks() {
  const checks = [];
  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
    checks.push(message);
  };
  const original = document.documentElement.outerHTML;
  const base = { rootSelector: "#fixture-email", waitForReady: true, sourceSHA256: "a".repeat(64), client: "fixture" };
  const result = await inspectEmailDOM(base);
  assert(result.ok, "Inspected the explicit email root");
  assert(result.root.rect.width === 600 && result.root.rect.x === 32, "Measured real CSS geometry");
  assert(result.readiness.ready && result.readiness.completedFrames === 2, "Waited for assets and two stable animation frames");
  assert(result.images[0].naturalWidth === 40 && result.images[0].rect.width === 80, "Distinguished natural and displayed image dimensions");
  assert(result.elements.some(element => element.overflow.horizontal), "Detected horizontal content overflow");
  assert(result.textNodes.some(node => node.text.includes("Alpha bravo") && node.rects.length > 1), "Captured wrapped text line rectangles");
  const serialized = JSON.stringify(result);
  assert(!/UNRELATED_APP_SECRET|URL_SECRET|FORM_SECRET|ATTRIBUTE_SECRET/.test(serialized), "Excluded app content and redacted private attributes and URL tokens");
  const query = await inspectEmailDOM({ rootSelector: "#fixture-email", querySelector: "#copy" });
  assert(query.ok && query.elements.length === 1 && query.textNodes.every(node => node.text.includes("Alpha bravo")), "Scoped an element query inside the email");
  const limited = await inspectEmailDOM({ rootSelector: "#fixture-email", maxElements: 1, maxHTMLChars: 128, maxTextChars: 10 });
  assert(limited.ok && limited.elements.length === 1 && limited.html.length <= 128 && limited.truncated.elements && limited.truncated.html && limited.truncated.textChars, "Enforced element, HTML and text bounds");
  const duplicate = await inspectEmailDOM({ rootSelector: ".duplicate" });
  assert(!duplicate.ok && duplicate.error.code === "ROOT_NOT_UNIQUE", "Rejected an ambiguous root selector");
  const app = await inspectEmailDOM({ rootSelector: "#fixture-shell" });
  assert(!app.ok && app.error.code === "SCOPE_TOO_BROAD", "Rejected an application root");
  const body = await inspectEmailDOM({ rootSelector: "body" });
  assert(!body.ok && body.error.code === "SCOPE_TOO_BROAD", "Rejected the full document body");
  const invalid = await inspectEmailDOM({ rootSelector: "[" });
  assert(!invalid.ok && invalid.error.code === "INVALID_SELECTOR", "Reported invalid CSS selectors");
  const absent = await inspectEmailDOM({ rootSelector: "#fixture-email", querySelector: ".absent" });
  assert(!absent.ok && absent.error.code === "QUERY_NOT_FOUND", "Reported a missing scoped query");
  const broken = await inspectEmailDOM({ rootSelector: "#broken-email", waitForReady: true });
  assert(broken.ok && broken.readiness.images.broken === 1 && !broken.readiness.ready, "Reported a failed image as not ready");
  const embedded = await inspectEmailDOM({ rootSelector: "#fixture-embedded", waitForReady: true });
  assert(embedded.ok && embedded.excludedEmbeddedDocuments === 1 && !JSON.stringify(embedded).includes("FRAME_SECRET") && !embedded.readiness.ready, "Skipped embedded documents without claiming readiness");
  assert(document.documentElement.outerHTML === original, "Left the live DOM unchanged");
  return { ok: true, count: checks.length, checks };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { runBrowserInspectionChecks };
  const { test } = require("node:test");
  const assert = require("node:assert/strict");
  const { inspectEmailDOM } = require("./browser-inspect.js");
  test("requires an explicit root and bounded options", async () => {
    for (const options of [undefined, {}, { rootSelector: "" }, { rootSelector: "#mail", maxElements: 2001 }, { rootSelector: "#mail", sourceSHA256: "unknown" }]) {
      assert.equal((await inspectEmailDOM(options)).error.code, "INVALID_OPTIONS");
    }
  });
  test("requires a real browser document for inspection", async () => {
    assert.equal((await inspectEmailDOM({ rootSelector: "#mail" })).error.code, "BROWSER_REQUIRED");
  });
}
({ testFunction: "runBrowserInspectionChecks" });
