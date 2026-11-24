/* Load as a classic browser script, then call inspectEmailDOM with an observed selector. */
async function inspectEmailDOM(options) {
  "use strict";

  const fail = (code, message) => ({ ok: false, error: { code, message } });
  if (!options || typeof options !== "object" || Array.isArray(options)) {
    return fail("INVALID_OPTIONS", "Pass an options object with rootSelector.");
  }
  const selector = options.rootSelector;
  if (typeof selector !== "string" || !selector.trim() || selector.length > 1000) {
    return fail("INVALID_OPTIONS", "rootSelector must be an explicit CSS selector, up to 1000 characters.");
  }
  if (options.querySelector !== undefined &&
      (typeof options.querySelector !== "string" || !options.querySelector.trim() || options.querySelector.length > 1000)) {
    return fail("INVALID_OPTIONS", "querySelector must be a nonempty CSS selector, up to 1000 characters.");
  }
  const limits = {
    maxElements: [250, 1, 2000],
    maxTextNodes: [200, 0, 2000],
    maxTextChars: [20000, 0, 100000],
    maxTextRects: [32, 1, 200],
    maxHTMLChars: [60000, 0, 250000],
    readinessTimeoutMs: [3000, 100, 10000],
  };
  const settings = {};
  for (const [key, [fallback, minimum, maximum]] of Object.entries(limits)) {
    const value = options[key] === undefined ? fallback : options[key];
    if (!Number.isInteger(value) || value < minimum || value > maximum) {
      return fail("INVALID_OPTIONS", `${key} must be an integer from ${minimum} to ${maximum}.`);
    }
    settings[key] = value;
  }
  if (options.waitForReady !== undefined && typeof options.waitForReady !== "boolean") {
    return fail("INVALID_OPTIONS", "waitForReady must be a boolean.");
  }
  if (options.sourceSHA256 !== undefined &&
      (typeof options.sourceSHA256 !== "string" || !/^[a-f\d]{64}$/i.test(options.sourceSHA256))) {
    return fail("INVALID_OPTIONS", "sourceSHA256 must be a 64-character SHA-256 hex digest.");
  }
  if (options.client !== undefined && (typeof options.client !== "string" || options.client.length > 120)) {
    return fail("INVALID_OPTIONS", "client must be a label of up to 120 characters.");
  }
  if (typeof document === "undefined" || !document.defaultView) {
    return fail("BROWSER_REQUIRED", "Run inside the document containing the observed email body.");
  }

  const doc = document;
  const win = doc.defaultView;
  let roots;
  try { roots = doc.querySelectorAll(selector); }
  catch { return fail("INVALID_SELECTOR", "rootSelector is not valid CSS."); }
  if (roots.length !== 1) {
    return fail("ROOT_NOT_UNIQUE", `rootSelector matched ${roots.length} elements; select exactly one email body.`);
  }
  const root = roots[0];
  const embeddedTags = new Set(["IFRAME", "FRAME", "OBJECT", "EMBED"]);
  const omittedTags = new Set(["SCRIPT", "NOSCRIPT", "TEMPLATE", "INPUT", "TEXTAREA", "SELECT"]);
  const role = (root.getAttribute("role") || "").toLowerCase();
  if (root === doc.body || root === doc.documentElement ||
      ["MAIN", "NAV", "HEADER"].includes(root.tagName) ||
      ["application", "main", "navigation", "toolbar"].includes(role) ||
      embeddedTags.has(root.tagName) || omittedTags.has(root.tagName) ||
      root.isContentEditable ||
      root.querySelector('[role="navigation"], [role="toolbar"], input[type="password"], [contenteditable="true"]')) {
    return fail("SCOPE_TOO_BROAD", "Select the email message body, excluding app chrome, editors and embedded documents.");
  }
  const descendants = root.querySelectorAll("*");
  if (descendants.length > 10000) {
    return fail("SCOPE_TOO_LARGE", "The root exceeds 10000 descendants; select a narrower email body.");
  }
  let matches;
  try {
    matches = options.querySelector
      ? Array.from(root.querySelectorAll(options.querySelector))
      : [root, ...descendants];
  } catch { return fail("INVALID_SELECTOR", "querySelector is not valid CSS."); }
  if (!matches.length) return fail("QUERY_NOT_FOUND", "querySelector did not match inside the email body.");
  const selected = matches.filter(node => !omittedTags.has(node.tagName));
  const elements = selected.slice(0, settings.maxElements);
  const rootImages = Array.from(root.querySelectorAll("img"));
  if (root.tagName === "IMG") rootImages.unshift(root);
  const excludedEmbeddedDocuments = Array.from(descendants).filter(node => embeddedTags.has(node.tagName)).length;
  const started = win.performance.now();
  const deadline = started + settings.readinessTimeoutMs;

  const round = value => Math.round(value * 1000) / 1000;
  function rect(node) {
    const r = node.getBoundingClientRect();
    return Object.fromEntries(["x", "y", "width", "height", "top", "right", "bottom", "left"].map(k => [k, round(r[k])]));
  }
  function path(node) {
    if (node === root) return "email";
    const parts = [];
    for (let current = node; current && current !== root; current = current.parentElement) {
      const parent = current.parentElement;
      if (!parent || !root.contains(current)) return null;
      parts.unshift(Array.prototype.indexOf.call(parent.children, current));
    }
    return `email/${parts.join("/")}`;
  }
  function safeURL(value) {
    if (!value) return value || "";
    if (/^data:/i.test(value)) return value.slice(0, value.indexOf(",") + 1) + "[data omitted]";
    if (/^(javascript|blob):/i.test(value)) return "[URL omitted]";
    try {
      const url = new URL(value, doc.baseURI);
      url.username = "";
      url.password = "";
      url.search = "";
      url.hash = "";
      return url.href.slice(0, 2048);
    } catch { return "[invalid URL]"; }
  }
  function safeCSS(value) {
    return value.replace(/url\(\s*(["']?)(.*?)\1\s*\)/gi, (_, quote, url) => `url("${safeURL(url)}")`);
  }
  const escapeText = value => value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const escapeAttribute = value => escapeText(value).replace(/"/g, "&quot;");
  const attributes = new Set([
    "id", "class", "style", "href", "src", "alt", "title", "width", "height", "role", "dir", "lang",
    "align", "valign", "bgcolor", "border", "cellpadding", "cellspacing", "colspan", "rowspan",
    "aria-label", "aria-hidden", "data-ogsc", "data-ogsb",
  ]);
  const voidTags = new Set(["AREA", "BASE", "BR", "COL", "HR", "IMG", "LINK", "META", "PARAM", "SOURCE", "WBR"]);
  const truncated = { elements: selected.length > elements.length, html: false, textNodes: false, textChars: false, textRects: false, images: false };
  let html = "";
  function append(value) {
    const remaining = settings.maxHTMLChars - html.length;
    if (value.length > remaining) truncated.html = true;
    html += value.slice(0, Math.max(0, remaining));
  }
  function serialize(node) {
    if (html.length >= settings.maxHTMLChars) { truncated.html = true; return; }
    if (node.nodeType === 3) { append(escapeText(node.nodeValue || "")); return; }
    if (node.nodeType !== 1 || omittedTags.has(node.tagName)) return;
    if (embeddedTags.has(node.tagName)) { append("<!-- embedded document omitted -->"); return; }
    let opening = `<${node.localName}`;
    for (const attribute of node.attributes) {
      if (!attributes.has(attribute.name)) continue;
      let value = attribute.value.slice(0, 4096);
      if (["src", "href"].includes(attribute.name)) value = safeURL(value);
      if (attribute.name === "style") value = safeCSS(value);
      opening += ` ${attribute.name}="${escapeAttribute(value)}"`;
    }
    append(opening + ">");
    if (voidTags.has(node.tagName)) return;
    if (node.tagName === "STYLE") append(safeCSS(node.textContent || ""));
    else for (const child of node.childNodes) { serialize(child); if (truncated.html) break; }
    append(`</${node.localName}>`);
  }

  function assetState() {
    const images = { total: rootImages.length, pending: 0, broken: 0 };
    for (const image of rootImages) {
      if (!image.complete) images.pending++;
      else if (!image.naturalWidth) images.broken++;
    }
    return { images, fonts: { supported: !!doc.fonts, status: doc.fonts ? doc.fonts.status : "unsupported" } };
  }
  function waitUntil(promise) {
    return new Promise(resolve => {
      let done = false;
      const finish = value => { if (!done) { done = true; win.clearTimeout(timer); resolve(value); } };
      const timer = win.setTimeout(() => finish(false), Math.max(0, deadline - win.performance.now()));
      promise.then(() => finish(true), () => finish(false));
    });
  }
  async function waitForImage(image) {
    if (image.complete) return;
    let finish;
    const pending = new Promise(resolve => { finish = resolve; image.addEventListener("load", finish, { once: true }); image.addEventListener("error", finish, { once: true }); });
    await waitUntil(pending);
    image.removeEventListener("load", finish);
    image.removeEventListener("error", finish);
  }
  function frame() {
    return new Promise(resolve => {
      const timeout = win.setTimeout(() => { win.cancelAnimationFrame(id); resolve(false); }, Math.max(0, deadline - win.performance.now()));
      const id = win.requestAnimationFrame(() => { win.clearTimeout(timeout); resolve(true); });
    });
  }
  let boundsStable = null;
  let completedFrames = 0;
  if (options.waitForReady) {
    await Promise.all([Promise.all(rootImages.map(waitForImage)), doc.fonts ? waitUntil(doc.fonts.ready) : Promise.resolve()]);
    const geometry = () => [root, ...elements.filter(node => node !== root)].map(node => JSON.stringify(rect(node))).join(";");
    const firstFrame = await frame();
    const first = geometry();
    const secondFrame = await frame();
    completedFrames = Number(firstFrame) + Number(secondFrame);
    boundsStable = completedFrames === 2 && first === geometry();
  }
  if (!root.isConnected) return fail("ROOT_DETACHED", "The email body changed during inspection; observe its selector again.");
  if (elements.some(node => node !== root && !root.contains(node)) ||
      rootImages.some(node => node !== root && !root.contains(node))) {
    return fail("ROOT_CHANGED", "Elements moved outside the email during inspection; observe its selector again.");
  }
  const rootRect = rect(root);
  const styleNames = [
    "display", "visibility", "opacity", "position", "box-sizing", "width", "height", "min-width", "max-width",
    "min-height", "max-height", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding-top", "padding-right", "padding-bottom", "padding-left", "overflow", "overflow-x", "overflow-y",
    "font-family", "font-size", "font-weight", "font-style", "line-height", "letter-spacing", "text-align",
    "white-space", "word-break", "overflow-wrap", "color", "background-color", "background-image",
    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width", "border-collapse",
    "table-layout", "vertical-align", "object-fit", "transform", "filter", "color-scheme",
  ];
  function inspectElement(node) {
    const computed = win.getComputedStyle(node);
    const box = rect(node);
    return {
      id: path(node), parentId: node === root ? null : path(node.parentElement), tag: node.localName,
      domId: (node.getAttribute("id") || "").slice(0, 256),
      className: (node.getAttribute("class") || "").slice(0, 1024),
      styles: Object.fromEntries(styleNames.map(name => [name, safeCSS(computed.getPropertyValue(name))])),
      rect: box,
      overflow: {
        horizontal: node.clientWidth > 0 && node.scrollWidth > node.clientWidth + 1,
        vertical: node.clientHeight > 0 && node.scrollHeight > node.clientHeight + 1,
        scrollWidth: node.scrollWidth, scrollHeight: node.scrollHeight,
        clientWidth: node.clientWidth, clientHeight: node.clientHeight,
        outsideRoot: box.left < rootRect.left - 1 || box.right > rootRect.right + 1 || box.top < rootRect.top - 1 || box.bottom > rootRect.bottom + 1,
      },
      embeddedDocumentSkipped: embeddedTags.has(node.tagName),
    };
  }
  const inspected = elements.map(inspectElement);
  const texts = [];
  let totalTextChars = 0;
  const inSelection = node => !options.querySelector || elements.some(element => element.contains(node));
  const walker = doc.createTreeWalker(root, win.NodeFilter.SHOW_TEXT);
  let textNode;
  while ((textNode = walker.nextNode())) {
    const parent = textNode.parentElement;
    const value = textNode.nodeValue || "";
    if (!value.trim() || !parent || !inSelection(textNode) ||
        parent.closest("script,style,noscript,template,input,textarea,select,iframe,object")) continue;
    if (texts.length >= settings.maxTextNodes) { truncated.textNodes = true; break; }
    const remaining = settings.maxTextChars - totalTextChars;
    if (remaining <= 0) { truncated.textChars = true; break; }
    const text = value.slice(0, remaining);
    if (text.length < value.length) truncated.textChars = true;
    totalTextChars += text.length;
    const range = doc.createRange();
    range.setStart(textNode, 0);
    range.setEnd(textNode, text.length);
    const boxes = Array.from(range.getClientRects());
    if (boxes.length > settings.maxTextRects) truncated.textRects = true;
    const textIndex = Array.from(parent.childNodes).filter(n => n.nodeType === 3).indexOf(textNode);
    texts.push({ id: `${path(parent)}/text/${textIndex}`, parentId: path(parent), text,
      rects: boxes.slice(0, settings.maxTextRects).map(box => Object.fromEntries(["x", "y", "width", "height"].map(k => [k, round(box[k])]))),
    });
  }
  const images = rootImages.slice(0, settings.maxElements).map(image => ({
    id: path(image), src: safeURL(image.getAttribute("src")), currentSrc: safeURL(image.currentSrc),
    alt: image.alt.slice(0, 2000), complete: image.complete,
    loaded: image.complete && image.naturalWidth > 0,
    broken: image.complete && image.naturalWidth === 0,
    naturalWidth: image.naturalWidth, naturalHeight: image.naturalHeight,
    width: image.width, height: image.height, rect: rect(image),
  }));
  truncated.images = rootImages.length > images.length;
  if (settings.maxHTMLChars) serialize(root);
  const assets = assetState();
  const assetsReady = assets.images.pending === 0 && assets.images.broken === 0 &&
    (!assets.fonts.supported || assets.fonts.status === "loaded");
  const fontFamilies = [...new Set(inspected.map(element => element.styles["font-family"]))];
  return {
    ok: true, schemaVersion: 1, capturedAt: new Date().toISOString(),
    client: options.client || null, sourceSHA256: options.sourceSHA256 || null,
    rootSelector: selector, querySelector: options.querySelector || null,
    root: { id: "email", tag: root.localName, rect: rootRect, descendantCount: descendants.length },
    html, elements: inspected, textNodes: texts, images,
    fonts: { ...assets.fonts, families: fontFamilies },
    readiness: {
      requested: !!options.waitForReady, assetsReady,
      ready: options.waitForReady ? assetsReady && boundsStable && excludedEmbeddedDocuments === 0 : null,
      checked: "Email img elements, document font loading and inspected element bounds. CSS background-image loading is not verified.",
      images: assets.images, boundsStable, completedFrames,
      timedOut: !!options.waitForReady && win.performance.now() >= deadline,
      elapsedMs: round(win.performance.now() - started),
    },
    excludedEmbeddedDocuments, truncated,
    redactions: ["URL credentials, query strings and fragments", "data/blob URLs", "unlisted attributes and form values", "scripts and embedded documents"],
    limits: settings,
  };
}

if (typeof module !== "undefined" && module.exports) module.exports = { inspectEmailDOM };
({ inspector: "inspectEmailDOM", schemaVersion: 1 });
