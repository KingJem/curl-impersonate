import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import { Builder, By } from "selenium-webdriver";
import firefox from "selenium-webdriver/firefox.js";


function option(name, fallback = undefined) {
  const prefix = `--${name}=`;
  const value = process.argv.find((argument) => argument.startsWith(prefix));
  return value ? value.slice(prefix.length) : fallback;
}


const executablePath = option("executable");
const driverPath = option("driver");
const label = option("label");
const output = option("output");
const url = option("url", "https://tls.browserleaks.com/json");

if (!executablePath || !driverPath || !label || !output) {
  throw new Error(
    "Usage: node capture-firefox-webdriver.mjs " +
      "--executable=/path/to/firefox --driver=/path/to/geckodriver " +
      "--label=firefox153 --output=output.json",
  );
}

const service = new firefox.ServiceBuilder(resolve(driverPath));
const options = new firefox.Options()
  .setBinary(resolve(executablePath))
  .addArguments("-headless");

const browser = await new Builder()
  .forBrowser("firefox")
  .setFirefoxOptions(options)
  .setFirefoxService(service)
  .build();

try {
  await browser.get(url);
  const rawDataTabs = await browser.findElements(
    By.xpath("//*[self::button or self::a][normalize-space()='Raw Data']"),
  );
  if (rawDataTabs.length > 0) {
    await rawDataTabs[0].click();
    await browser.sleep(100);
  }
  const bodyText = await browser.findElement(By.css("body")).getText();
  const jsonStart = bodyText.indexOf("{");
  const jsonEnd = bodyText.lastIndexOf("}");
  if (jsonStart < 0 || jsonEnd <= jsonStart) {
    throw new Error("Firefox JSON Viewer did not expose the raw response body");
  }
  const body = bodyText.slice(jsonStart, jsonEnd + 1);
  const payload = JSON.parse(body);
  const navigatorUserAgent = await browser.executeScript(
    "return navigator.userAgent",
  );
  const capabilities = await browser.getCapabilities();
  const capture = {
    capture: {
      label,
      url,
      captured_at: new Date().toISOString(),
      playwright_browser_version: null,
      webdriver_browser_version: capabilities.get("browserVersion"),
      navigator_user_agent: navigatorUserAgent,
    },
    fingerprint: payload,
  };

  const destination = resolve(output);
  await mkdir(dirname(destination), { recursive: true });
  await writeFile(destination, `${JSON.stringify(capture, null, 2)}\n`);
  console.log(JSON.stringify(capture, null, 2));
} finally {
  await browser.quit();
}
