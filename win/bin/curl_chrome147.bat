@echo off

set CURL_IMPERSONATE=chrome147

"%~dp0curl-impersonate.exe" --compressed --impersonate "chrome147" %*
