import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import { firefox } from "playwright";


function option(name, fallback = undefined) {
  const prefix = `--${name}=`;
  const value = process.argv.find((argument) => argument.startsWith(prefix));
  return value ? value.slice(prefix.length) : fallback;
}


const executablePath = option("executable");
const label = option("label");
const output = option("output");
const url = option("url", "https://tls.browserleaks.com/json");

if (!executablePath || !label || !output) {
  throw new Error(
    "Usage: node capture-firefox-fingerprint.mjs " +
      "--executable=/path/to/firefox --label=firefox150 --output=output.json",
  );
}

const browser = await firefox.launch({
  executablePath: resolve(executablePath),
  headless: true,
});

try {
  const context = await browser.newContext({ locale: "en-US" });
  const page = await context.newPage();
  const response = await page.goto(url, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  if (!response) {
    throw new Error(`No HTTP response received from ${url}`);
  }
  if (!response.ok()) {
    throw new Error(`Fingerprint endpoint returned HTTP ${response.status()}`);
  }

  const payload = JSON.parse((await response.body()).toString("utf8"));
  const navigatorUserAgent = await page.evaluate(() => navigator.userAgent);
  const capture = {
    capture: {
      label,
      url,
      captured_at: new Date().toISOString(),
      playwright_browser_version: browser.version(),
      navigator_user_agent: navigatorUserAgent,
    },
    fingerprint: payload,
  };

  const destination = resolve(output);
  await mkdir(dirname(destination), { recursive: true });
  await writeFile(destination, `${JSON.stringify(capture, null, 2)}\n`);
  console.log(JSON.stringify(capture, null, 2));
  await context.close();
} finally {
  await browser.close();
}
