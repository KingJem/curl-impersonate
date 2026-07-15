@echo off

set CURL_IMPERSONATE=chrome147_macos

"%~dp0curl-impersonate.exe" --compressed --impersonate "chrome147_macos" %*
