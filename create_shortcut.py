"""
Run once — creates a "Tracker" shortcut on the Desktop (pinnable to taskbar).
"""
import os
import subprocess

here = os.path.dirname(os.path.abspath(__file__))
vbs  = os.path.join(here, "start.vbs")
ico  = os.path.join(here, "icon.ico")

def ps(path):
    return path.replace("\\", "\\\\")

# Target must be wscript.exe (a real .exe) so Windows allows pinning to taskbar
script = f"""
$wscript  = "$env:SystemRoot\\System32\\wscript.exe"
$desktop  = [Environment]::GetFolderPath('Desktop')
$lnk      = Join-Path $desktop 'Tracker.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath       = $wscript
$s.Arguments        = '"{ps(vbs)}"'
$s.WorkingDirectory = '{ps(here)}'
$s.Description      = 'Time Tracker'
$s.IconLocation     = '{ps(ico)}'
$s.Save()
Write-Host "Shortcut created: $lnk"
"""

result = subprocess.run(
    ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
    capture_output=True, text=True
)

if result.returncode == 0:
    print(result.stdout.strip())
else:
    print("Error:")
    print(result.stderr)

input("Press Enter...")
