Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")
dir       = fso.GetParentFolderName(WScript.ScriptFullName)

' ── Перевіряємо чи є Python ──────────────────────────────────────────────
Function PythonExists()
    PythonExists = (shell.Run("cmd /c python --version", 0, True) = 0)
End Function

If Not PythonExists() Then
    ans = MsgBox( _
        "Python не знайдено на цьому комп'ютері." & vbCrLf & vbCrLf & _
        "Встановити останню версію Python автоматично (через winget)?", _
        vbQuestion + vbYesNo, "Трекер — потрібен Python" _
    )

    If ans = vbNo Then
        WScript.Quit
    End If

    ' ── Встановлюємо через winget ─────────────────────────────────────
    MsgBox _
        "Починаємо встановлення Python." & vbCrLf & _
        "Це займе 1-2 хвилини." & vbCrLf & vbCrLf & _
        "Натисніть OK і зачекайте — з'явиться вікно встановлення.", _
        vbInformation, "Трекер — встановлення Python"

    ret = shell.Run( _
        "cmd /c winget install --id Python.Python.3 -e " & _
        "--accept-package-agreements --accept-source-agreements " & _
        "--override ""/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1""", _
        1, True _
    )

    If ret = 0 Then
        MsgBox _
            "Python успішно встановлено!" & vbCrLf & vbCrLf & _
            "Натисніть OK — програма запуститься.", _
            vbInformation, "Трекер — готово"
        ' Перезапускаємо скрипт — нова сесія підхопить оновлений PATH
        shell.Run "wscript """ & WScript.ScriptFullName & """", 0
    Else
        MsgBox _
            "Не вдалося встановити Python автоматично." & vbCrLf & vbCrLf & _
            "Завантажте вручну з python.org (не забудьте галочку 'Add Python to PATH').", _
            vbCritical, "Трекер — помилка"
        shell.Run "https://www.python.org/downloads/"
    End If

    WScript.Quit
End If

' ── Python є — запускаємо (залежності встановляться автоматично) ──────────
shell.Run "pythonw """ & dir & "\main.pyw""", 1
