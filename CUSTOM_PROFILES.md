# curl-impersonate 本地编译与自定义浏览器指纹指南

本文档记录了在 macOS 上编译 curl-impersonate、添加 Tor Browser 指纹以及 Brave 浏览器指纹的完整过程。

---

## 目录

1. [环境依赖安装](#1-环境依赖安装)
2. [克隆与编译](#2-克隆与编译)
3. [安装到本地目录](#3-安装到本地目录)
4. [自定义浏览器指纹原理](#4-自定义浏览器指纹原理)
5. [添加 Tor Browser 指纹](#5-添加-tor-browser-指纹)
6. [添加 Brave 浏览器指纹](#6-添加-brave-浏览器指纹)
7. [增量重编译流程](#7-增量重编译流程)
8. [使用方法](#8-使用方法)
9. [已实现的自定义 Profile 一览](#9-已实现的自定义-profile-一览)

---

## 1. 环境依赖安装

```bash
brew install pkg-config make cmake ninja autoconf automake libtool
brew install zstd
brew install go
```

> **注意**：`ninja` 在 configure 阶段需要；`automake` 在编译 ngtcp2 时需要（提供 `aclocal`）。

---

## 2. 克隆与编译

```bash
git clone https://github.com/lexiforest/curl-impersonate.git
cd curl-impersonate

mkdir build && cd build
../configure

# macOS 使用 gmake（GNU Make）
gmake build
```

> **常见问题**：
> - `ninja not found` → `brew install ninja`
> - `aclocal not found` → `brew install automake`
> - `gmake install` 提示 permission denied `/usr/local` → 见第 3 节手动安装

---

## 3. 安装到本地目录

由于 `gmake install` 默认写入 `/usr/local`（需要 sudo），推荐安装到用户目录：

```bash
mkdir -p ~/.local/bin ~/.local/lib

# 复制动态库
\cp lib/.libs/libcurl-impersonate.4.dylib ~/.local/lib/

# 复制真实二进制（src/curl-impersonate 是 libtool wrapper，实际二进制在 .libs/）
\cp src/.libs/curl-impersonate /tmp/curl-impersonate-new

# 修正动态库路径（将编译时路径改为实际安装路径）
install_name_tool \
  -change /usr/local/lib/libcurl-impersonate.4.dylib \
          /Users/$USER/.local/lib/libcurl-impersonate.4.dylib \
  /tmp/curl-impersonate-new

\cp /tmp/curl-impersonate-new ~/.local/bin/curl-impersonate
chmod +x ~/.local/bin/curl-impersonate
```

验证安装：

```bash
~/.local/bin/curl-impersonate --impersonate chrome146 --compressed https://tls.browserleaks.com/json
```

---

## 4. 自定义浏览器指纹原理

### 4.1 核心文件

所有浏览器 Profile 定义在：

```
build/curl-8_15_0/lib/impersonate.c
```

该文件维护一个 `impersonations[]` 结构体数组，每个元素对应一个 `struct impersonate_opts`，定义了该 Profile 的全部 TLS 和 HTTP/2 参数。

### 4.2 关键字段说明

| 字段 | 说明 |
|---|---|
| `target` / `alias` | Profile 名称，传给 `--impersonate` 的值 |
| `ciphers` | TLS 密码套件列表（BoringSSL 格式） |
| `curves` | 椭圆曲线（TLS extension 10，支持的命名组） |
| `sig_hash_algs` | 签名哈希算法（TLS extension 13） |
| `tls_extension_order` | 扩展顺序，`NULL` 表示随机排列 |
| `tls_grease` | 是否发送 GREASE 值（Chrome 特征） |
| `tls_permute_extensions` | 是否随机排列 TLS 扩展（Chrome 110+ 特征） |
| `alpn` | 是否启用 ALPN 扩展 |
| `alps` | 是否启用 ALPS 扩展（Application-Layer Protocol Settings） |
| `tls_session_ticket` | 是否启用 Session Ticket |
| `cert_compression` | 证书压缩算法（`brotli` / `zlib` / `zstd`） |
| `http_headers` | HTTP 请求头列表（User-Agent、sec-ch-ua 等） |
| `http2_settings` | HTTP/2 SETTINGS 帧参数 |
| `http2_window_update` | HTTP/2 初始窗口大小 |
| `http2_pseudo_headers_order` | HTTP/2 伪头顺序（`masp` = Chrome，`mpas` = Firefox） |
| `http3_settings` | HTTP/3 SETTINGS 参数 |
| `quic_transport_parameters` | QUIC 传输参数 |
| `ech` | 是否启用 Encrypted Client Hello |
| `split_cookies` | 是否将多个 Cookie 拆分为多个 Cookie 头 |
| `form_boundary` | multipart/form-data boundary 风格（`webkit` / `firefox`） |

### 4.3 BoringSSL 注意事项

curl-impersonate 使用 BoringSSL（非 OpenSSL），以下算法/曲线 **不受支持**，添加时会报错：

- 曲线：`SecP256r1MLKEM768`、`secp224r1`
- 签名：`ed448`

---

## 5. 添加 Tor Browser 指纹

### 5.1 背景

Tor Browser 15.0.8 基于 Firefox 140.9.0（通过 `/Applications/Tor Browser.app/Contents/Resources/application.ini` 确认）。

Tor Browser 的 HTTPS 流量通过 Tor SOCKS 代理，由出口节点与目标服务器建立 TLS，因此浏览器本身的 TLS ClientHello 不直接可见。

真实的 Tor Browser TLS 指纹来自 **meek-lite 网桥流量**（packet 2967，目标 `192.42.116.12:443`，SNI: `www.mp35xnmwjb37dd4oz.com`）。

### 5.2 使用 Wireshark/tshark 抓取 TLS ClientHello

```bash
# 过滤 meek-lite 网桥流量
/Applications/Wireshark.app/Contents/MacOS/tshark \
  -r /tmp/wireshark_tor_session.pcapng \
  -Y "tls.handshake.type == 1 && ip.dst == 192.42.116.12" \
  -V 2>/dev/null | grep -E "Cipher Suite|Extension|Group|Sig"
```

### 5.3 Profile 实现要点

```
Profile 名：tor1508
Firefox 特征：
  - GREASE：关闭（tls_grease = false）
  - SCT：关闭（tls_signed_cert_timestamps = false）
  - HTTP/2 伪头顺序：mpas（Firefox 顺序）
  - 密码套件：Firefox 格式（TLS_ECDHE_* 命名）
  - 密钥共享限制：tls_key_shares_limit = 2
  - 扩展顺序：固定（"0-23-65281-10-11-16-5-34-51-43-13-28-65037"）
  - 证书压缩：zlib,brotli,zstd
  - form_boundary：firefox
```

### 5.4 指纹验证结果

```
JA3:  87339a9ac0381b25cee11a92d239dd7d
JA4:  t13d1710h2_5b57614c22b0_b23453fd2925
HTTP/2 akamai: 1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s
```

---

## 6. 添加 Brave 浏览器指纹

### 6.1 背景与技术依据

Brave 基于 Chromium，使用**完全相同的 TLS 栈（BoringSSL）**。

与 Chrome 的差异**仅体现在 HTTP 层**：

| 字段 | Chrome | Brave |
|---|---|---|
| `User-Agent` | `Chrome/X.0.0.0` | 相同（Brave 刻意不暴露自身） |
| `sec-ch-ua` | `"Google Chrome";v="X", "Chromium";v="X", ...` | `"Brave";v="X", "Chromium";v="X", "Not/A)Brand";v="24"` |
| `sec-ch-ua-platform` | 相同 | 相同 |
| TLS 指纹 | BoringSSL | 完全相同 |

参考：[Brave TLS Policy](https://github.com/brave/brave-browser/wiki/TLS-Policy) — "On all platforms except iOS, it currently uses the upstream Chromium implementation unmodified."

### 6.2 Brave 版本与 Chromium 对照

| Brave 版本 | Chromium 基础 | 发布时间 |
|---|---|---|
| 1.76.x | 134 | 2025-02 |
| 1.77.x | 135 | 2025-04 |
| ~1.78.x | 136 | 2025-05 |
| ~1.82.x | 145 | 2025-Q3 |

### 6.3 已实现的 Brave Profiles

在 `impersonate.c` 中，以下 6 个 Profile 已添加：

| Profile 名 | Chromium 基础 | 平台 | sec-ch-ua-mobile |
|---|---|---|---|
| `brave136_mac` | 136 | macOS | ?0 |
| `brave136_win` | 136 | Windows | ?0 |
| `brave136_android` | 136 | Android | ?1 |
| `brave145_mac` | 145 | macOS | ?0 |
| `brave145_win` | 145 | Windows | ?0 |
| `brave145_android` | 145 | Android | ?1 |

> Chromium 145+ 新增了 `http3_settings`、`quic_transport_parameters`、`sig_hash_algs`、`http3_tls_extension_order` 等 HTTP/3 相关参数。

### 6.4 指纹验证结果

| Profile | JA3 | JA4 |
|---|---|---|
| `brave136_mac` | `e7d8f006a33f14d4718f760fe314ab89` | `t13d1516h2_8daaf6152771_d8a2da3f94cd` |
| `brave136_win` | `20662fb360f02ea6a8200f0fd7801a6f` | `t13d1516h2_8daaf6152771_d8a2da3f94cd` |
| `brave136_android` | `5f8b79e023ff57f44f8d6bb5b09b69da` | `t13d1516h2_8daaf6152771_d8a2da3f94cd` |
| `brave145_mac` | `2b940c0d614db4766146f0f21327e44a` | `t13d1516h2_8daaf6152771_d8a2da3f94cd` |
| `brave145_win` | `4670e3521d5f3d77721e469ecbb149a0` | `t13d1516h2_8daaf6152771_d8a2da3f94cd` |
| `brave145_android` | `c6ba6472362f24c2d4cbafc1a4dd85c1` | `t13d1516h2_8daaf6152771_d8a2da3f94cd` |

**说明**：
- JA4 各 Profile 相同——JA4 对扩展排序后哈希，且剔除 GREASE，不受随机化影响
- JA3 各 Profile 不同——`tls_permute_extensions=true` 导致每次连接扩展顺序随机，JA3 因此不固定（这正是真实 Chrome/Brave 的行为）

---

## 7. 增量重编译流程

每次修改 `impersonate.c` 后，执行以下步骤更新安装：

```bash
cd /Users/king/WebstormProjects/curl_impersonate/build/curl-8_15_0

# 1. 删除旧的编译产物，强制重新编译 impersonate.c
\rm -f lib/libcurl_impersonate_la-impersonate.lo \
       lib/.libs/libcurl_impersonate_la-impersonate.o

# 2. 重新编译
/usr/bin/make

# 3. 安装动态库
\cp lib/.libs/libcurl-impersonate.4.dylib ~/.local/lib/

# 4. 安装二进制（需修正动态库路径）
\cp src/.libs/curl-impersonate /tmp/curl-impersonate-new
install_name_tool \
  -change /usr/local/lib/libcurl-impersonate.4.dylib \
          /Users/$USER/.local/lib/libcurl-impersonate.4.dylib \
  /tmp/curl-impersonate-new
\cp /tmp/curl-impersonate-new ~/.local/bin/curl-impersonate
```

> **为什么用 `\cp`**：macOS 默认 `cp` 是交互别名，`\cp` 绕过别名直接调用原始命令。

---

## 8. 使用方法

### 8.1 直接使用 curl-impersonate

```bash
~/.local/bin/curl-impersonate \
  --impersonate brave145_mac \
  --compressed \
  https://tls.browserleaks.com/json
```

### 8.2 使用 Wrapper 脚本

每个 Profile 有对应的 wrapper 脚本，自动添加 `--compressed` 和 `--impersonate` 参数：

```bash
# Brave 指纹
~/.local/bin/curl_brave136_mac     https://example.com
~/.local/bin/curl_brave136_win     https://example.com
~/.local/bin/curl_brave136_android https://example.com
~/.local/bin/curl_brave145_mac     https://example.com
~/.local/bin/curl_brave145_win     https://example.com
~/.local/bin/curl_brave145_android https://example.com

# Tor Browser 指纹
~/.local/bin/curl_tor1508          https://example.com
```

Wrapper 脚本内容模板：

```bash
#!/usr/bin/env bash
dir=${0%/*}
"$dir/curl-impersonate" --compressed --impersonate "brave145_mac" "$@"
```

### 8.3 验证 TLS 指纹

```bash
# 查看 JA3/JA4/UA 等信息
curl_brave145_mac https://tls.browserleaks.com/json | python3 -c \
  "import sys,json; d=json.load(sys.stdin); \
   print('JA3:', d.get('ja3_hash')); \
   print('JA4:', d.get('ja4')); \
   print('UA:', d.get('user_agent'))"
```

---

## 9. 已实现的自定义 Profile 一览

| Profile | 基础 | 平台 | 特点 |
|---|---|---|---|
| `tor1508` | Firefox 140 | macOS | Tor Browser 15.0.8，真实 meek-lite 流量抓包 |
| `brave136_mac` | Chrome 136 | macOS | Brave 1.78，sec-ch-ua 含 "Brave" |
| `brave136_win` | Chrome 136 | Windows | Brave 1.78，Windows UA |
| `brave136_android` | Chrome 136 | Android | Brave 1.78，Mobile UA |
| `brave145_mac` | Chrome 145 | macOS | Brave ~1.82，含 HTTP/3 参数 |
| `brave145_win` | Chrome 145 | Windows | Brave ~1.82，含 HTTP/3 参数 |
| `brave145_android` | Chrome 145 | Android | Brave ~1.82，含 HTTP/3 参数 |
| `chrome143_windows` | Chrome 143 | Windows | 兼容 `chrome145` TLS，平台头为 Windows |
| `chrome143_macos` | Chrome 143 | macOS | 兼容 `chrome145` TLS，平台头为 macOS |
| `chrome143_linux` | Chrome 143 | Linux | 兼容 `chrome145` TLS，平台头为 Linux |
| `chrome143_android` | Chrome 143 | Android | 兼容 `chrome131_android` TLS，平台头为 Android |
| `chrome143_ios` | Chrome 143 | iOS | 兼容 `safari260_ios` TLS，平台头为 iOS |
| `chrome144_windows` | Chrome 144 | Windows | 兼容 `chrome146` TLS，平台头为 Windows |
| `chrome144_macos` | Chrome 144 | macOS | 兼容 `chrome146` TLS，平台头为 macOS |
| `chrome144_linux` | Chrome 144 | Linux | 兼容 `chrome146` TLS，平台头为 Linux |
| `chrome144_android` | Chrome 144 | Android | 兼容 `chrome131_android` TLS，平台头为 Android |
| `chrome144_ios` | Chrome 144 | iOS | 兼容 `safari260_ios` TLS，平台头为 iOS |
| `chrome145_windows` | Chrome 145 | Windows | 平台化 Chrome 145 |
| `chrome145_macos` | Chrome 145 | macOS | 平台化 Chrome 145 |
| `chrome145_linux` | Chrome 145 | Linux | 平台化 Chrome 145 |
| `chrome145_android` | Chrome 145 | Android | 兼容 `chrome131_android` TLS，平台头为 Android |
| `chrome145_ios` | Chrome 145 | iOS | 兼容 `safari260_ios` TLS，平台头为 iOS |
| `chrome146_windows` | Chrome 146 | Windows | 平台化 Chrome 146 |
| `chrome146_macos` | Chrome 146 | macOS | 平台化 Chrome 146 |
| `chrome146_linux` | Chrome 146 | Linux | 平台化 Chrome 146 |
| `chrome146_android` | Chrome 146 | Android | 兼容 `chrome131_android` TLS，平台头为 Android |
| `chrome146_ios` | Chrome 146 | iOS | 兼容 `safari260_ios` TLS，平台头为 iOS |

---

## 10. tls-client 预设对照

`tls-client` 的 `profiles.go` 里有一批 preset，这个仓库里已经补上了能直接承接的浏览器家族入口。

| tls-client preset | 当前入口 | 状态 |
|---|---|---|
| `chrome_104` | `curl_chrome104` | native |
| `chrome_107` | `curl_chrome107` | native |
| `chrome_110` | `curl_chrome110` | native |
| `chrome_120` | `curl_chrome120` | native |
| `chrome_124` | `curl_chrome124` | native |
| `chrome_131` | `curl_chrome131` | native |
| `chrome_133` | `curl_chrome133a` | best-effort |
| `chrome_146` | `curl_chrome146` | native |
| `firefox_133` | `curl_firefox133` | native |
| `firefox_135` | `curl_firefox135` | native |
| `firefox_147` | `curl_firefox147` | native |
| `safari_ios_18_0` | `curl_safari180_ios` | native |
| `safari_ios_18_5` | `curl_safari184_ios` | best-effort |
| `safari_ios_26_0` | `curl_safari260_ios` | native |
| `brave_146` | `curl_brave145_*` | best-effort |
| `brave_146_PSK` | `curl_brave145_*` | best-effort |

除了上面这些自定义 profile，这次还补了 `chrome143_*`、`chrome144_*`、`chrome145_*` 和 `chrome146_*` 的平台变体，它们是基于现有 Chrome / Android / iOS TLS 模型做的 best-effort 别名。

其余 upstream preset 主要是 `okhttp4_android_*`、`zalando_*`、`mesh_*`、`mms_ios`、`confirmed_*` 这类 app-specific 指纹，curl-impersonate 目前没有对应的浏览器/TLS 模型，所以不在这个仓库里伪装成“已支持”。

---

## 附录：安装路径汇总

| 文件 | 路径 |
|---|---|
| 核心二进制 | `~/.local/bin/curl-impersonate` |
| 动态库 | `~/.local/lib/libcurl-impersonate.4.dylib` |
| Wrapper 脚本 | `~/.local/bin/curl_<profile>` |
| Profile 定义源码 | `build/curl-8_15_0/lib/impersonate.c` |
| Profile 头文件 | `build/curl-8_15_0/lib/impersonate.h` |
| Wireshark 抓包（Tor） | `/tmp/wireshark_tor_session.pcapng` |
