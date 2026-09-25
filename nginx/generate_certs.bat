@echo off
REM Скрипт генерации самоподписанного SSL-сертификата для Nginx (порты 80 / 443)
setlocal enabledelayedexpansion

set SSL_DIR=%~dp0ssl
if not exist "%SSL_DIR%" mkdir "%SSL_DIR%"

echo [*] Генерация SSL сертификата для localhost в %SSL_DIR%...
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout "%SSL_DIR%\key.pem" -out "%SSL_DIR%\cert.pem" -subj "/CN=localhost/O=ITEnterprise/C=RU"

if %ERRORLEVEL% EQU 0 (
    echo [+] Сертификат успешно создан:
    echo     cert.pem: %SSL_DIR%\cert.pem
    echo     key.pem:  %SSL_DIR%\key.pem
) else (
    echo [-] Ошибка при генерации сертификата. Проверьте наличие openssl.
)
pause
