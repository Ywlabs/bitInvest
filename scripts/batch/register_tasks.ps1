# 작업 스케줄러 등록 (콘솔 창 없이 VBS 실행)
# 관리자 PowerShell: .\scripts\batch\register_tasks.ps1

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Vbs = Join-Path $Root "scripts\batch\launch_worker.vbs"
$Wscript = "$env:SystemRoot\System32\wscript.exe"

if (-not (Test-Path $Vbs)) {
    Write-Error "launch_worker.vbs 를 찾을 수 없습니다: $Vbs"
}

function Register-BitInvestTask {
    param(
        [string]$Name,
        [string]$WorkerArg,
        [string[]]$ScheduleArgs
    )
    $tr = "`"$Wscript`" //B `"$Vbs`" $WorkerArg"
    Write-Host "등록: $Name"
    & schtasks /create /tn $Name /tr $tr @ScheduleArgs /f | Out-Null
}

Register-BitInvestTask -Name "bitInvest-Analysis" -WorkerArg "analysis" -ScheduleArgs @("/sc", "hourly", "/mo", "1")
Register-BitInvestTask -Name "bitInvest-Trading"  -WorkerArg "trading"  -ScheduleArgs @("/sc", "minute", "/mo", "15")
Register-BitInvestTask -Name "bitInvest-Report"   -WorkerArg "report"   -ScheduleArgs @("/sc", "daily", "/st", "23:00")

Write-Host ""
Write-Host "완료. 확인: schtasks /query /fo TABLE | findstr bitInvest"
Write-Host "이력 조회: python scripts/show_job_log.py"
