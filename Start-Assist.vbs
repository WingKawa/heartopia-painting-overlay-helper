Option Explicit
Dim shell, files, folder, executable
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
executable = files.BuildPath(folder, "venv\Scripts\pythonw.exe")
If Not files.FileExists(executable) Then
    MsgBox "Python environment not found. Use the portable executable instead.", 16, "Heartopia Painting Overlay Helper"
    WScript.Quit 1
End If
shell.CurrentDirectory = folder
shell.Run Chr(34) & executable & Chr(34) & " " & Chr(34) & files.BuildPath(folder, "run_assist.py") & Chr(34), 0, False
