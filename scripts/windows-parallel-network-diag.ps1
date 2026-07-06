#Requires -Version 5.1
<#
.SYNOPSIS
  Диагностика и автоисправление сетевых проблем Cursor Parallel на Windows.

.DESCRIPTION
  Проверяет типичные причины, из-за которых Parallel agents / Agent / Cloud subagents
  не имеют доступа в интернет на Windows:
  - системный proxy и переменные окружения
  - VPN/TUN адаптеры (Clash, Wintun и т.д.)
  - повреждённый cursor-socket (dist без out)
  - блокировка Cursor API доменов
  - остаточные Clash-сервисы

.PARAMETER Fix
  Применить безопасные автоисправления (сброс winhttp proxy, cursor-socket out).

.PARAMETER ExportLogs
  Скопировать последние логи Cursor в папку на рабочем столе.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\windows-parallel-network-diag.ps1
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\windows-parallel-network-diag.ps1 -Fix
#>

param(
    [switch]$Fix,
    [switch]$ExportLogs
)

$ErrorActionPreference = 'Continue'
$issues = [System.Collections.Generic.List[string]]::new()
$fixes  = [System.Collections.Generic.List[string]]::new()
$ok     = [System.Collections.Generic.List[string]]::new()

function Write-Section($title) {
    Write-Host ""
    Write-Host "=== $title ===" -ForegroundColor Cyan
}

function Add-Issue($msg)  { $issues.Add($msg);  Write-Host "[!] $msg" -ForegroundColor Red }
function Add-Fix($msg)    { $fixes.Add($msg);    Write-Host "[+] $msg" -ForegroundColor Green }
function Add-Ok($msg)     { $ok.Add($msg);       Write-Host "[ok] $msg" -ForegroundColor DarkGreen }

Write-Host "Cursor Parallel — диагностика сети Windows" -ForegroundColor White
Write-Host "Дата: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Режим Fix: $Fix"

# --- 1. Системный proxy ---
Write-Section "1. Системный proxy"

try {
    $winhttp = netsh winhttp show proxy 2>&1 | Out-String
    Write-Host $winhttp

    if ($winhttp -match 'Прямое подключение|Direct access|no proxy') {
        Add-Ok "WinHTTP proxy не настроен"
    } else {
        Add-Issue "WinHTTP proxy активен — частая причина сбоев Agent/Parallel"
        if ($Fix) {
            netsh winhttp reset proxy | Out-Null
            Add-Fix "WinHTTP proxy сброшен (netsh winhttp reset proxy)"
        }
    }
} catch {
    Add-Issue "Не удалось проверить WinHTTP proxy: $_"
}

$proxyReg = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
if ($proxyReg.ProxyEnable -eq 1 -and $proxyReg.ProxyServer) {
    Add-Issue "Пользовательский proxy в IE/Windows: $($proxyReg.ProxyServer)"
    if ($Fix) {
        Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 0
        Add-Fix "ProxyEnable отключён в реестре (HKCU)"
    }
} else {
    Add-Ok "Пользовательский proxy Windows выключен"
}

# --- 2. Переменные окружения ---
Write-Section "2. Переменные окружения proxy"

$envVars = @('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy','NO_PROXY')
$foundEnv = $false
foreach ($name in $envVars) {
    $userVal  = [Environment]::GetEnvironmentVariable($name, 'User')
    $machineVal = [Environment]::GetEnvironmentVariable($name, 'Machine')
    $procVal  = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ($userVal -or $machineVal -or $procVal) {
        $foundEnv = $true
        Add-Issue "$name = User:'$userVal' Machine:'$machineVal' Process:'$procVal'"
        if ($Fix -and ($userVal -or $machineVal)) {
            [Environment]::SetEnvironmentVariable($name, $null, 'User')
            [Environment]::SetEnvironmentVariable($name, $null, 'Machine')
            Add-Fix "Удалена переменная $name (User/Machine)"
        }
    }
}
if (-not $foundEnv) { Add-Ok "Proxy-переменные окружения не заданы" }

# --- 3. VPN / TUN адаптеры ---
Write-Section "3. VPN / TUN сетевые адаптеры"

$suspiciousPatterns = 'clash|wintun|tun|tap|mihomo|sing-box|v2ray|wireguard|openvpn|zerotier|tailscale'
$adapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match $suspiciousPatterns -or $_.InterfaceDescription -match $suspiciousPatterns
}

if ($adapters) {
    foreach ($a in $adapters) {
        Add-Issue "Подозрительный адаптер: $($a.Name) [$($a.InterfaceDescription)] Status=$($a.Status)"
    }
    Write-Host "    Рекомендация: удалите виртуальные адаптеры в Диспетчере устройств" -ForegroundColor Yellow
    Write-Host "    (Сетевые адаптеры → Wintun/Clash → Удалить + удалить драйвер)" -ForegroundColor Yellow
} else {
    Add-Ok "Подозрительные VPN/TUN адаптеры не найдены"
}

# --- 4. Clash-сервисы ---
Write-Section "4. Фоновые VPN-сервисы"

$services = Get-Service -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match 'clash|wintun|mihomo|v2ray|singbox' -or $_.DisplayName -match 'clash|wintun|mihomo|v2ray|singbox'
}
if ($services) {
    foreach ($s in $services) {
        Add-Issue "Сервис: $($s.DisplayName) ($($s.Name)) — $($s.Status)"
    }
} else {
    Add-Ok "Clash/Mihomo/v2ray сервисы не найдены"
}

# --- 5. cursor-socket ---
Write-Section "5. cursor-socket (EverythingProvider)"

$socketPaths = @(
    "$env:LOCALAPPDATA\Programs\cursor\resources\app\extensions\cursor-socket",
    "${env:ProgramFiles}\cursor\resources\app\extensions\cursor-socket"
)

$socketFixed = $false
foreach ($socketPath in $socketPaths) {
    if (-not (Test-Path $socketPath)) { continue }

    $dist = Join-Path $socketPath 'dist'
    $out  = Join-Path $socketPath 'out'

    if ((Test-Path $dist) -and -not (Test-Path $out)) {
        Add-Issue "cursor-socket: есть dist, но нет out → $socketPath"
        if ($Fix) {
            New-Item -ItemType Directory -Path $out -Force | Out-Null
            Copy-Item -Path (Join-Path $dist '*') -Destination $out -Recurse -Force
            Add-Fix "Скопирован dist → out в $socketPath"
            $socketFixed = $true
        }
    } elseif ((Test-Path $dist) -and (Test-Path $out)) {
        Add-Ok "cursor-socket OK: $socketPath"
    } else {
        Add-Issue "cursor-socket повреждён: $socketPath (нет dist)"
    }
}

if (-not ($socketPaths | Where-Object { Test-Path $_ })) {
    Add-Issue "Папка cursor-socket не найдена — Cursor установлен?"
}

# --- 6. Доступность Cursor API ---
Write-Section "6. Доступность Cursor API"

$domains = @(
    'https://api2.cursor.sh',
    'https://api5.cursor.sh',
    'https://authenticate.cursor.sh',
    'https://marketplace.cursorapi.com',
    'https://downloads.cursor.com'
)

foreach ($url in $domains) {
    try {
        $resp = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
        Add-Ok "$url → HTTP $($resp.StatusCode)"
    } catch {
        $code = $null
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        if ($code -in 200,301,302,403) {
            Add-Ok "$url → HTTP $code (доступен)"
        } else {
            Add-Issue "$url → недоступен: $($_.Exception.Message)"
        }
    }
}

# --- 7. Loopback (IPC extension host) ---
Write-Section "7. Loopback IPC (127.0.0.1)"

try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    Add-Ok "Loopback TCP OK (тестовый порт $port)"
} catch {
    Add-Issue "Loopback TCP заблокирован — антивирус/EDR может ломать Agent: $_"
}

# --- 8. Антивирус ---
Write-Section "8. Антивирус / EDR"

try {
    $av = Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction SilentlyContinue
    if ($av) {
        foreach ($p in $av) {
            Write-Host "    AV: $($p.displayName)"
            if ($p.displayName -match '360|Trend|Forcepoint|Kaspersky|Symantec|McAfee|CrowdStrike|Sentinel') {
                Add-Issue "Корпоративный/агрессивный AV: $($p.displayName) — добавьте исключения для Cursor.exe"
            }
        }
    } else {
        Write-Host "    (список AV недоступен — возможно, серверная/корпоративная ОС)"
    }
} catch {
    Write-Host "    Не удалось получить список AV: $_"
}

# --- 9. Настройки Cursor proxy ---
Write-Section "9. Настройки Cursor (settings.json)"

$settingsPaths = @(
    "$env:APPDATA\Cursor\User\settings.json",
    "$env:APPDATA\Cursor\User\profiles\*\settings.json"
)

foreach ($pattern in $settingsPaths) {
    Get-Item $pattern -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $json = Get-Content $_.FullName -Raw | ConvertFrom-Json
            $proxyKeys = @('http.proxy','http.proxySupport','cursor.general.disableHttp2')
            foreach ($key in $proxyKeys) {
                $parts = $key.Split('.')
                $val = $json
                foreach ($p in $parts) {
                    if ($val.PSObject.Properties.Name -contains $p) { $val = $val.$p } else { $val = $null; break }
                }
                if ($null -ne $val) {
                    Write-Host "    $($_.Name): $key = $val"
                    if ($key -eq 'http.proxy' -and "$val" -match '127\.0\.0\.1|localhost') {
                        Add-Issue "Cursor настроен на локальный proxy ($val) — если VPN выключен, Agent не подключится"
                    }
                    if ($key -eq 'cursor.general.disableHttp2' -and $val -eq $false) {
                        Write-Host "    Совет: при корпоративном proxy включите HTTP/1.1:" -ForegroundColor Yellow
                        Write-Host '    Cursor Settings → Network → HTTP Compatibility Mode → HTTP/1.1' -ForegroundColor Yellow
                    }
                }
            }
        } catch {
            Write-Host "    Не удалось прочитать $($_.FullName)"
        }
    }
}

# --- 10. Экспорт логов ---
if ($ExportLogs) {
    Write-Section "10. Экспорт логов Cursor"
    $logsRoot = "$env:APPDATA\Cursor\logs"
    if (Test-Path $logsRoot) {
        $latest = Get-ChildItem $logsRoot -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $dest = Join-Path $env:USERPROFILE "Desktop\cursor-logs-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Copy-Item $latest.FullName $dest -Recurse -Force
        Add-Fix "Логи скопированы: $dest"
    } else {
        Add-Issue "Папка логов не найдена: $logsRoot"
    }
}

# --- Итог ---
Write-Section "ИТОГ"

Write-Host "Проблем найдено: $($issues.Count)" -ForegroundColor $(if ($issues.Count) { 'Red' } else { 'Green' })
Write-Host "Исправлений применено: $($fixes.Count)" -ForegroundColor Green

if ($issues.Count -eq 0) {
    Write-Host ""
    Write-Host "Явных проблем не найдено." -ForegroundColor Green
    Write-Host "Если Parallel всё ещё без интернета:" -ForegroundColor Yellow
    Write-Host "  1. Cursor Settings → Network → Run Diagnostics (скриншот)" -ForegroundColor Yellow
    Write-Host "  2. Cursor Settings → Network → HTTP Compatibility Mode → HTTP/1.1" -ForegroundColor Yellow
    Write-Host "  3. Полный перезапуск Cursor (не Reload Window)" -ForegroundColor Yellow
    Write-Host "  4. Запуск: cursor --disable-extensions" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Найденные проблемы:" -ForegroundColor Red
    $issues | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }

    if (-not $Fix) {
        Write-Host ""
        Write-Host "Запустите с -Fix для автоисправления:" -ForegroundColor Yellow
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\windows-parallel-network-diag.ps1 -Fix" -ForegroundColor Yellow
    }
}

if ($Fix -and ($socketFixed -or $fixes.Count -gt 0)) {
    Write-Host ""
    Write-Host "Перезапустите Cursor полностью после применения исправлений." -ForegroundColor Green
}

Write-Host ""
exit $(if ($issues.Count -gt 0) { 1 } else { 0 })
