/* Run the browser checks only on tests/gmail-inspect.html. */
async function runGmailInspectionChecks() {
  if (document.title !== "Gmail inspector fixture") throw new Error("Open the dedicated Gmail fixture first.");
  const checks = [];
  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
    checks.push(message);
  };
  const options = { gmailMessageId: "2222", expectedSubject: "Fixture inserted email", sourceSHA256: "b".repeat(64), timeoutMs: 2000 };
  let settled = false;
  const pending = inspectInsertedGmail(options).then(result => { settled = true; return result; });
  document.querySelector("h2.hP").textContent = options.expectedSubject;
  await new Promise(resolve => requestAnimationFrame(resolve));
  assert(!settled, "Did not accept the previous message body after the heading changed");
  const container = document.createElement("div");
  container.className = "adn ads";
  container.setAttribute("data-legacy-message-id", "2222");
  container.innerHTML = '<div class="a3s aiL"><p>Inserted fixture content</p><p>Update Email Preference</p></div>';
  document.body.append(container);
  const result = await pending;
  assert(result.ok && result.readiness.ready && result.nativeIdentity.gmailMessageId === "2222" && result.nativeIdentity.endingPresent, "Inspected the exact newly inserted message");
  assert(!/PREVIOUS_MESSAGE_BODY|UNRELATED_GMAIL_SHELL/.test(JSON.stringify(result)), "Excluded the previous message and Gmail shell");
  container.querySelector(".a3s.aiL").textContent = "The expected ending is missing";
  const missing = await inspectInsertedGmail({ ...options, timeoutMs: 100 });
  assert(!missing.ok && missing.error.code === "GMAIL_ENDING_NOT_FOUND" && !missing.nativeIdentity.endingPresent, "Rejected a body with a missing ending");
  const wrongID = await inspectInsertedGmail({ ...options, gmailMessageId: "3333", timeoutMs: 100 });
  assert(!wrongID.ok && wrongID.error.code === "GMAIL_MESSAGE_TIMEOUT", "Rejected a correct heading with the wrong API message ID");
  return { ok: true, count: checks.length, checks };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { runGmailInspectionChecks };
  const { test } = require("node:test");
  const assert = require("node:assert/strict");
  const { inspectInsertedGmail } = require("./gmail-inspect.js");
  const valid = { gmailMessageId: "1a20f77735f50dac", expectedSubject: "Fixture", sourceSHA256: "a".repeat(64) };
  test("requires exact insertion identity and bounded wait", async () => {
    for (const options of [undefined, {}, { ...valid, gmailMessageId: 'bad"selector' }, { ...valid, expectedSubject: "" }, { ...valid, expectedEnding: "" }, { ...valid, timeoutMs: 60001 }]) {
      assert.equal((await inspectInsertedGmail(options)).error.code, "INVALID_OPTIONS");
    }
  });
  test("requires a browser document", async () => {
    assert.equal((await inspectInsertedGmail(valid)).error.code, "BROWSER_REQUIRED");
  });
}
({ testFunction: "runGmailInspectionChecks" });
