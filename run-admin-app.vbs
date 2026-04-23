Option Explicit

Dim shell, fso, root, pythonw, app, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = fso.BuildPath(root, ".venv\Scripts\pythonw.exe")
app = fso.BuildPath(root, "admin_app.py")

If Not fso.FileExists(pythonw) Then
  MsgBox "Missing Python runtime: " & pythonw, vbCritical, "AI Assist"
  WScript.Quit 1
End If

If Not fso.FileExists(app) Then
  MsgBox "Missing app entrypoint: " & app, vbCritical, "AI Assist"
  WScript.Quit 1
End If

cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & app & Chr(34)
shell.Run cmd, 0, False
