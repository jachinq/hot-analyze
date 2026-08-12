#Requires -Version 7.0
<#
.SYNOPSIS
    一键启动 hot-analyze 后端 API 与前端开发服务（PowerShell 7+）。

.DESCRIPTION
    默认通过 Windows Terminal 在当前窗口开两个新 Tab：
      - 后端：uv run uvicorn（http://127.0.0.1:8000）
      - 前端：pnpm dev（http://127.0.0.1:5173）
    -NewWindow：改为各开独立窗口；-Attached：当前终端同时托管（Ctrl+C 一并退出）。

.PARAMETER SkipInstall
    跳过依赖安装（uv sync / pnpm install）。

.PARAMETER Attached
    在当前终端附加运行两个进程，而不是打开 Tab / 窗口。

.PARAMETER NewWindow
    使用独立控制台窗口（不经过 Windows Terminal Tab）。

.EXAMPLE
    .\start.ps1
.EXAMPLE
    .\start.ps1 -SkipInstall
.EXAMPLE
    .\start.ps1 -Attached
.EXAMPLE
    .\start.ps1 -NewWindow
#>
[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$Attached,
    [switch]$NewWindow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = $PSScriptRoot
$FrontendDir = Join-Path $Root 'frontend'
$ApiHost = '0.0.0.0'
$ApiPort = 8000
$WebPort = 5173

function Repair-ProcessPath {
    # Cursor / 某些宿主会裁掉 System32，导致 pnpm/vite 无法 spawn cmd.exe
    $required = @(
        (Join-Path $env:SystemRoot 'System32'),
        (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0'),
        (Join-Path $env:SystemRoot 'SysWOW64'),
        $env:SystemRoot
    )
    $parts = @($env:Path -split ';' | Where-Object { $_ })
    foreach ($dir in $required) {
        if ($dir -and (Test-Path -LiteralPath $dir) -and ($parts -notcontains $dir)) {
            $parts = @($dir) + $parts
        }
    }
    $env:Path = ($parts -join ';')
}

Repair-ProcessPath

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Message)
    Write-Host "    $Message" -ForegroundColor DarkGray
}

function Assert-Command {
    param(
        [Parameter(Mandatory)][string]$Name,
        [string]$Hint
    )
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        $msg = "未找到命令：$Name"
        if ($Hint) { $msg += "。$Hint" }
        throw $msg
    }
}

function Ensure-EnvFile {
    $envPath = Join-Path $Root '.env'
    $examplePath = Join-Path $Root '.env.example'
    if (-not (Test-Path $envPath) -and (Test-Path $examplePath)) {
        Copy-Item $examplePath $envPath
        Write-Info "已从 .env.example 复制生成 .env，请按需填写密钥。"
    }
}

function Install-Dependencies {
    Write-Step '安装 / 同步依赖'
    Push-Location $Root
    try {
        Write-Info 'uv sync ...'
        & uv sync
        if ($LASTEXITCODE -ne 0) { throw "uv sync 失败（exit $LASTEXITCODE）" }

        if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
            throw '未找到 pnpm。请先安装：npm install -g pnpm 或启用 corepack'
        }
        Write-Info 'pnpm install ...'
        Push-Location $FrontendDir
        try {
            & pnpm install
            if ($LASTEXITCODE -ne 0) { throw "pnpm install 失败（exit $LASTEXITCODE）" }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        Pop-Location
    }
}

function Resolve-PwshPath {
    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $PSHOME 'pwsh.exe'),
        (Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe'),
        (Join-Path $env:ProgramFiles 'PowerShell\7-preview\pwsh.exe')
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    throw '未找到 PowerShell 7+（pwsh）。请安装：https://aka.ms/powershell'
}

function Resolve-WtPath {
    $cmd = Get-Command wt -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\wt.exe'),
        (Join-Path $env:ProgramFiles 'Windows Terminal\wt.exe')
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    return $null
}

function New-ServiceRunnerScripts {
    <#
    .SYNOPSIS
        生成临时启动脚本，避免 wt / Start-Process 传参转义问题。
    #>
    $dir = Join-Path ([System.IO.Path]::GetTempPath()) 'hot-analyze-dev'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $pathRepair = @'
$required = @(
    (Join-Path $env:SystemRoot 'System32'),
    (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0'),
    $env:SystemRoot
)
$parts = @($env:Path -split ';' | Where-Object { $_ })
foreach ($d in $required) {
    if ($d -and (Test-Path -LiteralPath $d) -and ($parts -notcontains $d)) {
        $parts = @($d) + $parts
    }
}
$env:Path = ($parts -join ';')
'@

    $apiScript = Join-Path $dir 'run-api.ps1'
    $webScript = Join-Path $dir 'run-web.ps1'

    @"
#Requires -Version 7.0
Set-StrictMode -Version Latest
`$ErrorActionPreference = 'Stop'
$pathRepair
Set-Location -LiteralPath '$Root'
`$Host.UI.RawUI.WindowTitle = 'hot-analyze API :$ApiPort'
Write-Host '启动后端 API → http://127.0.0.1:$ApiPort' -ForegroundColor Green
Write-Host 'OpenAPI     → http://127.0.0.1:$ApiPort/docs' -ForegroundColor DarkGray
uv run uvicorn app.main:app --reload --host $ApiHost --port $ApiPort
"@ | Set-Content -LiteralPath $apiScript -Encoding utf8

    @"
#Requires -Version 7.0
Set-StrictMode -Version Latest
`$ErrorActionPreference = 'Stop'
$pathRepair
Set-Location -LiteralPath '$FrontendDir'
`$Host.UI.RawUI.WindowTitle = 'hot-analyze Web :$WebPort'
Write-Host '启动前端 → http://127.0.0.1:$WebPort' -ForegroundColor Green
pnpm dev -- --host 127.0.0.1 --port $WebPort
"@ | Set-Content -LiteralPath $webScript -Encoding utf8

    [pscustomobject]@{
        ApiScript = $apiScript
        WebScript = $webScript
    }
}

function Start-InTerminalTabs {
    Write-Step '在 Windows Terminal 当前窗口打开新 Tab'
    $wtPath = Resolve-WtPath
    if (-not $wtPath) {
        Write-Info '未找到 wt.exe，回退为独立窗口模式'
        Start-InNewWindows
        return
    }

    $pwshPath = Resolve-PwshPath
    $runners = New-ServiceRunnerScripts

    # 不能用 Start-Process -ArgumentList：它会把参数拼成字符串再拆，
    # 导致 "C:\Program Files\..." 空格把 wt 参数解析打乱（0x80070002）。
    # 使用调用运算符按 argv 逐项传递，并用 -- 分隔 wt 选项与要启动的命令。
    & $wtPath -w 0 new-tab `
        --title "hot-analyze-API:$ApiPort" `
        -d $Root `
        -- $pwshPath -NoExit -NoLogo -File $runners.ApiScript
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Windows Terminal 打开 API Tab 失败（exit $LASTEXITCODE）"
    }

    & $wtPath -w 0 new-tab `
        --title "hot-analyze-Web:$WebPort" `
        -d $FrontendDir `
        -- $pwshPath -NoExit -NoLogo -File $runners.WebScript
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Windows Terminal 打开 Web Tab 失败（exit $LASTEXITCODE）"
    }

    Write-Host ''
    Write-Host '已在当前 Windows Terminal 窗口打开两个 Tab：' -ForegroundColor Green
    Write-Info "后端  → http://127.0.0.1:$ApiPort  (docs: /docs)"
    Write-Info "前端  → http://127.0.0.1:$WebPort"
    Write-Host ''
    Write-Host '关闭对应 Tab 即可停止服务。' -ForegroundColor Yellow
    Write-Host '若从 Cursor 集成终端运行，Tab 会出现在 Windows Terminal 窗口中（非 Cursor 面板）。' -ForegroundColor DarkGray
}

function Start-InNewWindows {
    Write-Step '在新终端窗口启动服务'
    $pwshPath = Resolve-PwshPath
    $runners = New-ServiceRunnerScripts
    $childEnv = @{ Path = $env:Path }

    $backend = Start-Process -FilePath $pwshPath -ArgumentList @(
        '-NoExit', '-NoLogo', '-File', $runners.ApiScript
    ) -WorkingDirectory $Root -PassThru -Environment $childEnv

    $frontend = Start-Process -FilePath $pwshPath -ArgumentList @(
        '-NoExit', '-NoLogo', '-File', $runners.WebScript
    ) -WorkingDirectory $FrontendDir -PassThru -Environment $childEnv

    Write-Host ''
    Write-Host '已启动：' -ForegroundColor Green
    Write-Info "后端 PID $($backend.Id)  → http://127.0.0.1:$ApiPort  (docs: /docs)"
    Write-Info "前端 PID $($frontend.Id)  → http://127.0.0.1:$WebPort"
    Write-Host ''
    Write-Host '关闭对应终端窗口即可停止服务。' -ForegroundColor Yellow
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)
    if ($null -eq $Process) { return }
    try {
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($Process.Id)" -ErrorAction SilentlyContinue |
            ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
    catch { }
}

function Start-Attached {
    Write-Step '在当前终端附加启动（Ctrl+C 同时停止）'

    $logDir = Join-Path ([System.IO.Path]::GetTempPath()) 'hot-analyze-dev'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $backendOut = Join-Path $logDir 'api.out.log'
    $backendErr = Join-Path $logDir 'api.err.log'
    $frontendOut = Join-Path $logDir 'web.out.log'
    $frontendErr = Join-Path $logDir 'web.err.log'
    foreach ($f in @($backendOut, $backendErr, $frontendOut, $frontendErr)) {
        if (Test-Path $f) { Remove-Item $f -Force }
        New-Item -ItemType File -Path $f -Force | Out-Null
    }

    $backend = Start-Process -FilePath 'uv' -ArgumentList @(
        'run', 'uvicorn', 'app.main:app',
        '--reload', '--host', $ApiHost, '--port', "$ApiPort"
    ) -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr `
        -Environment @{ Path = $env:Path }

    $frontend = Start-Process -FilePath 'pnpm' -ArgumentList @(
        'dev', '--', '--host', '127.0.0.1', '--port', "$WebPort"
    ) -WorkingDirectory $FrontendDir -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr `
        -Environment @{ Path = $env:Path }

    Write-Host ''
    Write-Host '服务已启动：' -ForegroundColor Green
    Write-Info "后端 PID $($backend.Id)  → http://127.0.0.1:$ApiPort  (docs: /docs)"
    Write-Info "前端 PID $($frontend.Id)  → http://127.0.0.1:$WebPort"
    Write-Info "日志目录：$logDir"
    Write-Host ''

    $offsets = @{}
    foreach ($f in @($backendOut, $backendErr, $frontendOut, $frontendErr)) {
        $offsets[$f] = 0L
    }

    function Read-NewLogLines {
        foreach ($path in @($backendOut, $backendErr, $frontendOut, $frontendErr)) {
            if (-not (Test-Path -LiteralPath $path)) { continue }
            $info = Get-Item -LiteralPath $path
            if ($info.Length -le $offsets[$path]) { continue }
            $fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            try {
                $null = $fs.Seek($offsets[$path], [System.IO.SeekOrigin]::Begin)
                $reader = [System.IO.StreamReader]::new($fs)
                try {
                    while ($null -ne ($line = $reader.ReadLine())) {
                        $prefix = if ($path -like '*api*') { '[API]' } else { '[WEB]' }
                        $color = if ($path -like '*api*') { 'Blue' } else { 'Magenta' }
                        Write-Host "$prefix $line" -ForegroundColor $color
                    }
                    $offsets[$path] = $fs.Position
                }
                finally {
                    $reader.Dispose()
                }
            }
            finally {
                $fs.Dispose()
            }
        }
    }

    try {
        while ($true) {
            Read-NewLogLines
            if ($backend.HasExited -or $frontend.HasExited) {
                Start-Sleep -Milliseconds 300
                Read-NewLogLines
                $codeApi = if ($backend.HasExited) { $backend.ExitCode } else { 'running' }
                $codeWeb = if ($frontend.HasExited) { $frontend.ExitCode } else { 'running' }
                Write-Host "有进程已退出（API=$codeApi, Web=$codeWeb），正在收尾…" -ForegroundColor Yellow
                break
            }
            Start-Sleep -Milliseconds 250
        }
    }
    finally {
        Stop-ProcessTree $backend
        Stop-ProcessTree $frontend
        Write-Host "`n已停止前后端进程。" -ForegroundColor Yellow
    }
}

# ---- main ----
Write-Host 'hot-analyze 一键启动' -ForegroundColor Magenta
Write-Info "项目目录：$Root"
Write-Info "PowerShell：$($PSVersionTable.PSVersion)"

Assert-Command -Name 'uv' -Hint '请安装 uv：https://docs.astral.sh/uv/'
Assert-Command -Name 'pnpm' -Hint '请安装 pnpm，或执行：corepack enable && corepack prepare pnpm@latest --activate'
$null = Resolve-PwshPath

if (-not (Test-Path (Join-Path $FrontendDir 'package.json'))) {
    throw "未找到前端目录：$FrontendDir"
}

Ensure-EnvFile

if (-not $SkipInstall) {
    Install-Dependencies
}
else {
    Write-Info '已跳过依赖安装（-SkipInstall）'
}

if ($Attached -and $NewWindow) {
    throw '参数冲突：请只使用 -Attached 或 -NewWindow 之一'
}

if ($Attached) {
    Start-Attached
}
elseif ($NewWindow) {
    Start-InNewWindows
}
else {
    Start-InTerminalTabs
}
