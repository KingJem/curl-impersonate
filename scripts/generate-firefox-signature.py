#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

import yaml


SIGNATURE_IDS = {
    "ecdsa_secp256r1_sha256": 1027,
    "ecdsa_secp384r1_sha384": 1283,
    "ecdsa_secp521r1_sha512": 1539,
    "rsa_pss_rsae_sha256": 2052,
    "rsa_pss_rsae_sha384": 2053,
    "rsa_pss_rsae_sha512": 2054,
    "rsa_pkcs1_sha256": 1025,
    "rsa_pkcs1_sha384": 1281,
    "rsa_pkcs1_sha512": 1537,
    "ecdsa_sha1": 515,
    "rsa_pkcs1_sha1": 513,
}
COMPRESSION_IDS = {"zlib": 1, "brotli": 2, "zstd": 3}
PSEUDO_HEADERS = {"m": ":method", "p": ":path", "a": ":authority", "s": ":scheme"}


def numeric_suffix(value: str) -> int:
    matches = re.findall(r"\((\d+)\)", value)
    if not matches:
        raise ValueError(f"No numeric suffix in {value!r}")
    return int(matches[-1])


def extension_map(tls: dict) -> dict[int, dict]:
    return {numeric_suffix(item["name"]): item for item in tls["extensions"]}


def signature_ids(values: list[str]) -> list[int]:
    return [SIGNATURE_IDS[value] for value in values]


def render_extension(extension_id: int, extension: dict) -> dict:
    if extension_id == 0:
        return {"type": "server_name"}
    if extension_id == 23:
        return {"length": 0, "type": "extended_master_secret"}
    if extension_id == 65281:
        return {"length": 1, "type": "renegotiation_info"}
    if extension_id == 10:
        groups = [numeric_suffix(value) for value in extension["supported_groups"]]
        return {
            "length": 2 + 2 * len(groups),
            "supported_groups": groups,
            "type": "supported_groups",
        }
    if extension_id == 11:
        return {"ec_point_formats": [0], "length": 2, "type": "ec_point_formats"}
    if extension_id == 35:
        return {"length": 0, "type": "session_ticket"}
    if extension_id == 16:
        protocols = extension["protocols"]
        length = 2 + sum(1 + len(value) for value in protocols)
        return {
            "alpn_list": protocols,
            "length": length,
            "type": "application_layer_protocol_negotiation",
        }
    if extension_id == 5:
        return {"length": 5, "status_request_type": 1, "type": "status_request"}
    if extension_id == 34:
        algorithms = signature_ids(extension["signature_hash_algorithms"])
        return {
            "length": 2 + 2 * len(algorithms),
            "sig_hash_algs": algorithms,
            "type": "delegated_credentials",
        }
    if extension_id == 18:
        return {"length": 0, "type": "signed_certificate_timestamp"}
    if extension_id == 51:
        shares = []
        payload_length = 2
        for share in extension["shared_keys"]:
            name, value = next(iter(share.items()))
            length = len(value) // 2
            shares.append({"group": numeric_suffix(name), "length": length})
            payload_length += 4 + length
        return {"key_shares": shares, "length": payload_length, "type": "keyshare"}
    if extension_id == 43:
        return {
            "length": 5,
            "supported_versions": ["TLS_VERSION_1_3", "TLS_VERSION_1_2"],
            "type": "supported_versions",
        }
    if extension_id == 13:
        algorithms = signature_ids(extension["signature_algorithms"])
        return {
            "length": 2 + 2 * len(algorithms),
            "sig_hash_algs": algorithms,
            "type": "signature_algorithms",
        }
    if extension_id == 45:
        return {"length": 2, "psk_ke_mode": 1, "type": "psk_key_exchange_modes"}
    if extension_id == 28:
        return {
            "length": 2,
            "record_size_limit": int(extension["data"]),
            "type": "record_size_limit",
        }
    if extension_id == 27:
        algorithms = [
            COMPRESSION_IDS[re.sub(r" \(\d+\)$", "", value)]
            for value in extension["algorithms"]
        ]
        return {
            "algorithms": algorithms,
            "length": 1 + 2 * len(algorithms),
            "type": "compress_certificate",
        }
    if extension_id == 65037:
        return {"length": 0, "type": "encrypted_client_hello"}
    raise ValueError(f"Unsupported Firefox extension {extension_id}")


def parse_http2(payload: dict) -> dict:
    settings_text, window_update, _, pseudo_order = payload["akamai_fingerprint"].split("|")
    settings = [
        {"key": int(key), "value": int(value)}
        for key, value in (item.split(":", 1) for item in settings_text.split(";"))
    ]
    headers_frame = next(
        frame for frame in payload["sent_frames"] if frame["frame_type"] == "HEADERS"
    )
    headers = [value for value in headers_frame["headers"] if not value.startswith(":")]
    return {
        "frames": [
            {"frame_type": "SETTINGS", "settings": settings, "stream_id": 0},
            {
                "frame_type": "WINDOW_UPDATE",
                "stream_id": 0,
                "window_size_increment": int(window_update),
            },
            {
                "frame_type": "HEADERS",
                "headers": headers,
                "pseudo_headers": [PSEUDO_HEADERS[value] for value in pseudo_order.split(",")],
                "stream_id": headers_frame["stream_id"],
            },
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("peet", type=Path)
    parser.add_argument("browserleaks", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    peet = json.loads(args.peet.read_text())["fingerprint"]
    browserleaks = json.loads(args.browserleaks.read_text())["fingerprint"]
    tls = peet["tls"]
    extensions = extension_map(tls)
    extension_order = [int(value) for value in tls["ja3"].split(",")[2].split("-")]
    ciphers = [int(value) for value in tls["ja3"].split(",")[1].split("-")]

    signature = {
        "browser": {"name": "firefox", "os": "macOS", "version": args.version},
        "signature": {
            "http2": parse_http2(peet["http2"]),
            "tls_client_hello": {
                "ciphersuites": ciphers,
                "comp_methods": [0],
                "extensions": [
                    render_extension(extension_id, extensions[extension_id])
                    for extension_id in extension_order
                ],
                "handshake_version": "TLS_VERSION_1_2",
                "record_version": "TLS_VERSION_1_0",
                "session_id_length": 32,
            },
        },
        "third_party": {
            "user_agent": browserleaks["user_agent"],
            "ja3_hash": browserleaks["ja3_hash"],
            "ja3_text": browserleaks["ja3_text"],
            "ja3n_hash": browserleaks["ja3n_hash"],
            "ja3n_text": browserleaks["ja3n_text"],
            "akamai_hash": browserleaks["akamai_hash"],
            "akamai_text": browserleaks["akamai_text"],
        },
    }
    args.output.write_text(yaml.safe_dump(signature, sort_keys=False, width=120))


if __name__ == "__main__":
    main()
