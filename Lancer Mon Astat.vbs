' Lance Mon Astat (NovaKit à jour) sans console
Option Explicit
Dim shell, fso, dir, pythonw, mainPy
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = "C:\Users\lutre\Desktop\NovaKit"
mainPy = dir & "\main.py"
shell.CurrentDirectory = dir
shell.Environment("PROCESS")("PYTHONPATH") = dir

pythonw = shell.ExpandEnvironmentStrings("%LocalAppData%\Programs\Python\Python312\pythonw.exe")
If Not fso.FileExists(pythonw) Then
  pythonw = shell.ExpandEnvironmentStrings("%LocalAppData%\Programs\Python\Python313\pythonw.exe")
End If

If fso.FileExists(pythonw) Then
  shell.Run """" & pythonw & """ """ & mainPy & """", 0, False
Else
  shell.Run "pyw -3 """ & mainPy & """", 0, False
End If
