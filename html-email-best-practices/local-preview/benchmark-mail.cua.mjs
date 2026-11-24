// Run from CUA's Node runtime, passing its documented native-app API.
export async function benchmarkMailTrial({ cua, fs, execFile, base, trial, outputDir }) {
  const html = await fs.readFile(trial.referenceFile);
  const started = performance.now();
  const result = {
    trial: trial.trial, client: 'apple-mail', marker: trial.marker,
    sourceSHA256: trial.sourceSHA256, startedAt: new Date().toISOString(),
    stagesSeconds: {}, observationRecoveries: [],
    boundary: 'Before saving revised HTML through fresh native evidence returned and saved.',
  };
  const elapsed = () => +((performance.now() - started) / 1000).toFixed(3);
  let mail;
  let top;
  let last;
  try {
    await fs.mkdir(outputDir, { recursive: true, mode: 0o700 });
    await fs.writeFile(outputDir + '/email.html', html, { mode: 0o600 });
    const prepared = await execFile('python3', [base + '/preview.py', 'prepare',
      '--html', outputDir + '/email.html', '--clients', 'apple-mail',
      '--state-dir', outputDir + '/prepared']);
    result.run = JSON.parse(prepared.stdout);
    if (result.run.sourceSha256 !== trial.sourceSHA256 || result.run.assetIssues) {
      throw Error('The prepared source did not match the shared revision.');
    }
    result.stagesSeconds.prepared = elapsed();
    let finder = await cua.getApp('com.apple.finder');
    // A fresh app binding also recovers occasional stale native capture handles.
    const observeFinder = async () => {
      try { return await finder.getAXState({ emit: false, disableDiffing: true }); }
      catch {
        result.observationRecoveries.push({ atSeconds: elapsed(), action: 'Rebound Finder observation once.' });
        finder = await cua.getApp('com.apple.finder');
        return await finder.getAXState({ emit: false, disableDiffing: true });
      }
    };
    await finder.pressKey('super+shift+g');
    const pathState = await observeFinder();
    const field = pathState.match(/^\s*(\d+) text field.*ID: PathTextField/m);
    if (!field) throw Error('Finder did not expose the path field.');
    await finder.setValue(Number(field[1]), result.run.runDir + '/message.eml');
    await finder.pressKey('Return');
    const selected = await observeFinder();
    if (!selected.includes(result.run.runId) || !selected.includes('image (selected) message.eml')) {
      throw Error('Finder did not select the exact current message file.');
    }
    result.stagesSeconds.selected = elapsed();
    await finder.pressKey('super+o');
    await observeFinder();
    mail = await cua.getApp('com.apple.mail');
    let ax = await mail.getAXState({ emit: false, disableDiffing: true });
    if (!ax.includes(result.run.subject) || !ax.includes(trial.marker) || !ax.includes('Update Email Preference')) {
      throw Error('Native subject, current revision marker or complete ending was missing.');
    }
    await fs.writeFile(outputDir + '/mail-ax.txt', ax, { mode: 0o600 });
    result.inspectionFile = outputDir + '/mail-ax.txt';
    result.stagesSeconds.accessibilityReturned = elapsed();
    top = await mail.getScreenshot({ emit: false });
    await fs.writeFile(outputDir + '/mail-top.jpg', top, { mode: 0o600 });
    result.firstImageSeconds = elapsed();
    result.screenshotFiles = [outputDir + '/mail-top.jpg'];
    result.ok = true;
    result.artifactCoverage = 'Complete native accessibility text plus initial desktop viewport screenshot.';
    // Keep overlapping native viewports until the actual message scroll reaches its end.
    for (let index = 1; index <= 5; index++) {
      ax = await mail.getAXState({ emit: false, disableDiffing: true });
      const area = ax.match(/^\s*(\d+) scroll area Description: message content/m);
      if (!area) throw Error('Mail did not expose its message scroll area.');
      await mail.scroll(Number(area[1]), 'down', 1);
      const state = await mail.getAXState({ emit: false, disableDiffing: true });
      last = await mail.getScreenshot({ emit: false });
      if (!last) throw Error('Mail did not return a native viewport screenshot.');
      const path = outputDir + '/mail-scroll-' + index + '.jpg';
      await fs.writeFile(path, last, { mode: 0o600 });
      result.screenshotFiles.push(path);
      const scroll = state.match(/scroll bar \(settable, float\) ([0-9.]+)/);
      if (scroll && Number(scroll[1]) >= 0.999) {
        result.fullMessageImageSetSeconds = elapsed();
        break;
      }
    }
    if (!result.fullMessageImageSetSeconds) throw Error('The screenshot sequence did not reach the message ending.');
    result.ok = true;
    result.artifactCoverage = 'Complete native accessibility text plus overlapping message viewports through the bottom.';
  } catch (error) {
    if (result.firstImageSeconds) result.fullMessageCaptureError = error.message;
    else { result.ok = false; result.error = error.message; }
    result.elapsedSeconds = elapsed();
  }
  await fs.mkdir(outputDir, { recursive: true, mode: 0o700 });
  await fs.writeFile(outputDir + '/result.json', JSON.stringify(result, null, 2) + '\n', { mode: 0o600 });
  return { result, mail, top, last };
}
