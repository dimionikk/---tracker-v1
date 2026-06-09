Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")
dir       = fso.GetParentFolderName(WScript.ScriptFullName)

' Перевіряємо чи встановлено Python
result = shell.Run("cmd /c python --version", 0, True)

If result <> 0 Then
    ans = MsgBox( _
        "Python не знайдено на цьому комп'ютері." & vbCrLf & vbCrLf & _
        "Завантажте Python 3.10+ з python.org та встановіть його." & vbCrLf & _
        "Під час встановлення обов'язково поставте галочку:" & vbCrLf & _
        "  ""Add Python to PATH""" & vbCrLf & vbCrLf & _
        "Відкрити сторінку завантаження?", _
        vbQuestion + vbYesNo, "Трекер — потрібен Python" _
    )
    If ans = vbYes Then
        shell.Run "https://www.python.org/downloads/"
    End If
    WScript.Quit
End If

' Python є — запускаємо (залежності встановляться автоматично)
shell.Run "pythonw """ & dir & "\tracker.pyw""", 1
