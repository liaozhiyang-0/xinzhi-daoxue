[CmdletBinding()]
param(
    [int]$Port = 8000,
    [int]$Rounds = 10,
    [int]$TaskTimeoutSeconds = 180,
    [string]$OutputPath = ".codex-tmp\release-a-cold-matrix.jsonl"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$BaseUrl = "http://127.0.0.1:$Port"
$Supervisor = Join-Path $PSScriptRoot "xzd_supervisor.ps1"
$OutputFile = Join-Path $Root $OutputPath

function Write-Record([object]$Record) {
    $line = $Record | ConvertTo-Json -Depth 10 -Compress
    Add-Content -LiteralPath $OutputFile -Value $line -Encoding UTF8
    Write-Output $line
}

function Get-Health {
    Invoke-RestMethod "$BaseUrl/api/v1/health" -TimeoutSec 10
}

function Get-Architecture {
    (Invoke-RestMethod "$BaseUrl/api/v1/observability/summary" -TimeoutSec 10).architecture
}

function Wait-Ready {
    for ($attempt = 1; $attempt -le 36; $attempt++) {
        try {
            $health = Get-Health
            if ($health.status -eq "ok" -and $health.configuration_status -eq "ready") {
                return $health
            }
        } catch {
            # Startup is expected to be unavailable during this bounded wait.
        }
        Start-Sleep -Seconds 5
    }
    throw "API did not become ready within 180 seconds."
}

function Stop-Project {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Supervisor -Stop -Port $Port | Out-Null
}

function Start-Project {
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Supervisor,
        "-Port", "$Port"
    ) -WorkingDirectory $Root -WindowStyle Hidden | Out-Null
    return Wait-Ready
}

function New-Task([string]$SessionId, [string]$UserId, [string]$Intent, [string]$Text) {
    $payload = @{
        session_id = $SessionId
        user_id = $UserId
        user_role = "student"
        scene = "solving"
        course_id = "CT"
        intent = $Intent
        canonical_input = @{ text = $Text }
        attachments = @()
        context_refs = @()
        options = @{}
        response_depth = "brief"
    } | ConvertTo-Json -Depth 8
    Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/tasks" `
        -ContentType "application/json" -Body $payload -TimeoutSec 30
}

function Wait-Task([string]$TaskId, [string]$UserId) {
    $deadline = (Get-Date).AddSeconds($TaskTimeoutSeconds)
    do {
        Start-Sleep -Seconds 3
        $task = Invoke-RestMethod "$BaseUrl/api/v1/tasks/$TaskId`?user_id=$UserId" -TimeoutSec 30
    } while ($task.status -notin @("completed", "failed", "cancelled") -and (Get-Date) -lt $deadline)
    return $task
}

New-Item -ItemType Directory -Path (Split-Path -Parent $OutputFile) -Force | Out-Null
Remove-Item -LiteralPath $OutputFile -Force -ErrorAction SilentlyContinue

for ($round = 1; $round -le $Rounds; $round++) {
    $roundStarted = Get-Date
    $health = $null
    try {
        Stop-Project
        $health = Start-Project
        $userId = "rc_exec_01_round_$round"
        $session = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/sessions" `
            -ContentType "application/json" -Body (@{
                user_id = $userId
                course_id = "CT"
                title = "RC-EXEC-01 cold round $round"
            } | ConvertTo-Json) -TimeoutSec 30

        $cases = @(
            @{ intent = "explain_concept"; text = "解释一下戴维宁定理的物理意义。" },
            @{ intent = "solve_problem"; text = "一个10Ω电阻接在20V理想电压源两端，求电流和电阻吸收功率。" },
            @{ intent = "explain_concept"; text = "运算放大器虚短在什么条件下可以使用？" }
        )
        $tasks = foreach ($case in $cases) {
            $created = New-Task $session.id $userId $case.intent $case.text
            $result = Wait-Task $created.id $userId
            $surface = $result.input_content.options._execution_surface
            [ordered]@{
                task_id = $created.id
                intent = $case.intent
                status = $result.status
                failure_category = $result.failure_category
                result_present = ($null -ne $result.result_content)
                runtime_generation = $surface.runtime_generation
                build_id = $surface.build_id
                canonical_plan_version = $surface.canonical_plan_version
                startup_fingerprint = $surface.startup_fingerprint
            }
        }
        $architecture = Get-Architecture
        Write-Record ([ordered]@{
            round = $round
            started_at = $roundStarted.ToString("o")
            finished_at = (Get-Date).ToString("o")
            health = [ordered]@{
                status = $health.status
                database = $health.database
                redis = $health.redis
                minio = $health.minio
                configuration_status = $health.configuration_status
            }
            tasks = @($tasks)
            architecture = $architecture
        })
    } catch {
        Write-Record ([ordered]@{
            round = $round
            started_at = $roundStarted.ToString("o")
            finished_at = (Get-Date).ToString("o")
            error = $_.Exception.Message
        })
        throw
    }
}
