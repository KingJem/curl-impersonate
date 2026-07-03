# Firefox 150, 152, and 153 Profiles

The `firefox150`, `firefox152`, and `firefox153` profiles are based on live
captures from `tls.browserleaks.com/json` and `tls.peet.ws/api/all`.

## Browser Builds

| Profile | Browser build | Automation | Platform |
|---|---|---|---|
| `firefox150` | Firefox 150.0.2, Playwright revision 1522 | Playwright 1.60.0 | macOS arm64 |
| `firefox152` | Firefox 152.0b1, Playwright beta revision 1526 | Playwright 1.61.1 | macOS arm64 |
| `firefox153` | Firefox Nightly 153.0a1, 2026-06-15 mozilla-central | geckodriver 0.37.0 | macOS arm64 |

Playwright 1.61.1 and the latest 1.62 alpha did not include a patched Firefox
153 build at capture time. Stock Firefox does not implement Playwright's
`-juggler-pipe`, so Firefox 153 was controlled through Mozilla's WebDriver
instead. The browser making the network request was the official Firefox
153.0a1 Nightly build.

## Install Playwright Browsers

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-firefox-150 \
  npx -y playwright@1.60.0 install firefox

PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-firefox-152 \
  npx -y playwright@1.61.1 install firefox-beta
```

The Firefox 153 Nightly used for the capture is archived at:

```text
https://ftp.mozilla.org/pub/firefox/nightly/2026/06/
2026-06-15-09-30-07-mozilla-central/firefox-153.0a1.en-US.mac.dmg
```

## Capture Commands

The capture scripts require `playwright` or `selenium-webdriver` to be
installed in the Node environment that runs them.

```bash
node scripts/capture-firefox-fingerprint.mjs \
  --executable=/path/to/firefox \
  --label=firefox150_macos \
  --output=tests/captures/firefox_150.0.2_macos_browserleaks.json

node scripts/capture-firefox-webdriver.mjs \
  --executable=/path/to/firefox-nightly \
  --driver=/path/to/geckodriver \
  --label=firefox153_nightly_macos \
  --output=tests/captures/firefox_153.0a1_macos_browserleaks.json
```

Use `--url=https://tls.peet.ws/api/all` to capture detailed ClientHello,
headers, and HTTP/2 frame data.

## Generate Profiles And Signatures

```bash
python3 scripts/generate-firefox-profile.py \
  tests/captures/firefox_150.0.2_macos_peet.json \
  --target firefox150

python3 scripts/generate-firefox-signature.py \
  tests/captures/firefox_150.0.2_macos_peet.json \
  tests/captures/firefox_150.0.2_macos_browserleaks.json \
  --version 150.0.2 \
  --output tests/signatures/firefox_150.0.2_macOS.yaml
```

Repeat the commands with the 152 and 153 capture files.

## Observed Differences

| Property | Firefox 150 | Firefox 152 | Firefox 153 |
|---|---|---|---|
| JA3 hash | `6447ab086255d194909d4013b1a89e87` | `424f6d9c8b8928c0a0489a4f1a0f3e89` | `424f6d9c8b8928c0a0489a4f1a0f3e89` |
| JA4 | `t13d1617h2_86a278354501_3cbfd9057e0d` | `t13d1517h2_8daaf6152771_68c5a8c2958d` | `t13d1517h2_8daaf6152771_68c5a8c2958d` |
| ECDSA AES-256 CBC cipher | Present | Removed | Removed |
| ECDSA SHA-1 signature | Present | Removed | Removed |
| TLS key shares | 3 | 3 | 2 |
| Record size limit | 4001 | 4001 | 4001 |
| HTTP/2 fingerprint | `1:65536;2:0;4:131072;5:16384\|12517377\|0\|m,p,a,s` | Same | Same |

The raw capture files are committed under `tests/captures/` so future profile
changes can be reviewed against the source evidence.
