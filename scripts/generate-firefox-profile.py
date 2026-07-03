#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


HEADER_NAMES = {
    "user-agent": "User-Agent",
    "accept": "Accept",
    "accept-language": "Accept-Language",
    "accept-encoding": "Accept-Encoding",
    "upgrade-insecure-requests": "Upgrade-Insecure-Requests",
    "sec-fetch-dest": "Sec-Fetch-Dest",
    "sec-fetch-mode": "Sec-Fetch-Mode",
    "sec-fetch-site": "Sec-Fetch-Site",
    "sec-fetch-user": "Sec-Fetch-User",
    "priority": "Priority",
    "te": "Te",
}

HTTP3_SETTINGS = "1:65536;7:20;727725890:0;16765559:1;51:1;8:1"
HTTP3_TRANSPORT_PARAMETERS = (
    "1:30000;4:25165824;5:12582912;6:1048576;7:1048576;8:100;"
    "9:100;11:20;14:8;15:AUTO;17:1@GREASE,1;GREASE;32:65535"
)
HTTP3_EXTENSION_ORDER = "28-51-27-13-34-10-45-16-65281-23-5-0-43-57-65037"


def extension_id(extension: dict) -> int:
    matches = re.findall(r"\((\d+)\)", extension["name"])
    if not matches:
        raise ValueError(f"Extension has no numeric ID: {extension['name']}")
    return int(matches[-1])


def extension_map(tls: dict) -> dict[int, dict]:
    return {extension_id(item): item for item in tls["extensions"]}


def names(values: list[str]) -> list[str]:
    return [re.sub(r" \(\d+\)$", "", value) for value in values]


def c_string_lines(values: list[str], indent: str = "      ") -> list[str]:
    lines = []
    for index, value in enumerate(values):
        if index < len(values) - 1:
            lines.append(f'{indent}"{value}:"')
        else:
            lines.append(f'{indent}"{value}",')
    return lines


def parse_headers(http2: dict) -> list[str]:
    frame = next(item for item in http2["sent_frames"] if item["frame_type"] == "HEADERS")
    headers = []
    for line in frame["headers"]:
        if line.startswith(":"):
            continue
        key, value = line.split(": ", 1)
        headers.append(f"{HEADER_NAMES.get(key, key)}: {value}")
    return headers


def render_profile(capture_path: Path, target: str) -> str:
    payload = json.loads(capture_path.read_text())["fingerprint"]
    tls = payload["tls"]
    http2 = payload["http2"]
    extensions = extension_map(tls)

    ciphers = tls["ciphers"]
    curves = names(extensions[10]["supported_groups"])
    signatures = extensions[13]["signature_algorithms"]
    delegated = extensions[34]["signature_hash_algorithms"]
    compression = names(extensions[27]["algorithms"])
    order = "-".join(str(extension_id(item)) for item in tls["extensions"])
    headers = parse_headers(http2)
    settings, window_update, _, pseudo_order = http2["akamai_fingerprint"].split("|")
    priority = next(
        item for item in http2["sent_frames"] if item["frame_type"] == "HEADERS"
    )["priority"]
    key_share_count = len(extensions[51]["shared_keys"])

    lines = [
        "  {",
        f'    .target = "{target}",',
        f'    .alias = "{target}",',
        "    .httpversion = CURL_HTTP_VERSION_2_0,",
        "    .ssl_version = CURL_SSLVERSION_TLSv1_2 | CURL_SSLVERSION_MAX_DEFAULT,",
        "    .ciphers =",
        *c_string_lines(ciphers),
        "    .http_headers = {",
    ]
    for index, header in enumerate(headers):
        suffix = "," if index < len(headers) - 1 else ""
        lines.append(f'      "{header}"{suffix}')
    lines.extend(
        [
            "    },",
            f'    .curves = "{":".join(curves)}",',
            "    .sig_hash_algs =",
            *c_string_lines(signatures),
            "    .alpn = true,",
            f'    .http2_settings = "{settings}",',
            f"    .http2_window_update = {window_update},",
            f'    .http2_pseudo_headers_order = "{pseudo_order.replace(",", "")}",',
            f"    .http2_stream_exclusive = {int(priority['exclusive'])},",
            f"    .http2_stream_weight = {priority['weight']},",
            f'    .http3_settings = "{HTTP3_SETTINGS}",',
            '    .http3_pseudo_headers_order = "msap",',
            f'    .quic_transport_parameters = "{HTTP3_TRANSPORT_PARAMETERS}",',
            f'    .http3_tls_extension_order = "{HTTP3_EXTENSION_ORDER}",',
            f'    .cert_compression = "{",".join(compression)}",',
            f'    .ech = "{"true" if 65037 in extensions else "false"}",',
            f"    .tls_session_ticket = {'true' if 35 in extensions else 'false'},",
            f'    .tls_extension_order = "{order}",',
            f'    .tls_delegated_credentials = "{":".join(delegated)}",',
            f"    .tls_record_size_limit = {extensions[28]['data']},",
            "    .tls_grease = false,",
            f"    .tls_signed_cert_timestamps = {'true' if 18 in extensions else 'false'},",
            f"    .tls_key_shares_limit = {key_share_count},",
            "    .split_cookies = true,",
            '    .form_boundary = "firefox",',
            "  },",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rendered = render_profile(args.capture, args.target) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
