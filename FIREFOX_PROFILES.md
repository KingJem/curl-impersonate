# Firefox 150, 152, and 153 Profiles

The `firefox150`, `firefox152`, and `firefox153` profiles are based on live
captures from `tls.browserleaks.com/json` and `tls.peet.ws/api/all`.

Platform (Windows / Linux) variants of Firefox 150–153 are documented in
[Windows and Linux Variants](#windows-and-linux-variants) below.

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

## Windows and Linux Variants

The base `firefox150`/`firefox151`/`firefox152`/`firefox153` profiles carry a
macOS (or, for `firefox151`, a Windows) User-Agent. To impersonate Firefox on
other desktop platforms, the following per-OS variants are provided:

| Profile | Version | Platform | Wrapper |
|---|---|---|---|
| `firefox150_windows` | 150.0.2 | Windows 10 | `curl_firefox150_windows` |
| `firefox150_linux`   | 150.0.2 | Linux      | `curl_firefox150_linux` |
| `firefox151_windows` | 151.0   | Windows 10 | `curl_firefox151_windows` |
| `firefox151_linux`   | 151.0   | Linux      | `curl_firefox151_linux` |
| `firefox152_windows` | 152.0b1 | Windows 10 | `curl_firefox152_windows` |
| `firefox152_linux`   | 152.0b1 | Linux      | `curl_firefox152_linux` |
| `firefox153_windows` | 153.0a1 | Windows 10 | `curl_firefox153_windows` |
| `firefox153_linux`   | 153.0a1 | Linux      | `curl_firefox153_linux` |

### How they are derived

Firefox uses **NSS**, whose TLS ClientHello is **operating-system independent**,
and Firefox does **not** send `sec-ch-ua`. The only observable per-OS difference
is the `User-Agent` string. Each variant therefore reuses the corresponding base
profile's already-verified TLS / HTTP2 / HTTP3 signature unchanged and only
swaps the User-Agent (the same approach as the pre-existing `firefox135_win`):

```
Windows: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:V.0) Gecko/20100101 Firefox/V.0
Linux:   Mozilla/5.0 (X11; Linux x86_64; rv:V.0) Gecko/20100101 Firefox/V.0
```

These variants were **not** re-captured from a live browser; they are derived
from the base profiles above. Their test signatures under `tests/signatures/`
(`firefox_<version>_{win10,linux}.yaml`) are clones of the corresponding base
signature with only the User-Agent (and `os`/`version` metadata) changed, so the
test suite still verifies the emitted ClientHello and HTTP/2 frames field by
field.

### firefox151 note

`firefox151` has no upstream capture. It is identical to `firefox152` except for
`record_size_limit` (16385 vs 4001) and `accept-language`, so its signature is
derived from `firefox152` with just those two fields adjusted.
