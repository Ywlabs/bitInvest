' Worker 숨김 실행 (작업 스케줄러용 — 콘솔 창 없음)
' 사용: wscript.exe //B launch_worker.vbs analysis

Option Explicit

Dim fso, shell, batchDir, root, pythonw, cmd, workerKey, exitCode

If WScript.Arguments.Count < 1 Then
    WScript.Quit 2
End If

workerKey = LCase(WScript.Arguments(0))

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

batchDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(fso.GetParentFolderName(batchDir))

pythonw = root & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(pythonw) Then
    WScript.Quit 1
End If

Select Case workerKey
    Case "analysis"
        cmd = """" & pythonw & """ """ & root & "\scripts\run_analysis_watch.py"""
    Case "trading"
        cmd = """" & pythonw & """ """ & root & "\scripts\run_trading_consumer.py"""
    Case "report"
        cmd = """" & pythonw & """ """ & root & "\scripts\run_report.py"""
    Case "pipeline"
        cmd = """" & pythonw & """ """ & root & "\scripts\run_pipeline.py"" --event-only"
    Case Else
        WScript.Quit 2
End Select

exitCode = shell.Run(cmd, 0, True)
WScript.Quit exitCode
