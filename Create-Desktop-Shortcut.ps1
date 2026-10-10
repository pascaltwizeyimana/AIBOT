$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $projectRoot "Launch-App.vbs"
$iconPath = Join-Path $projectRoot "pacbot-app.ico"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "PACBOT.lnk"

Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap(64, 64)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::FromArgb(19, 29, 27))

$gold = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(225, 183, 92), 4)
$mint = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(108, 202, 167), 3)
$font = New-Object System.Drawing.Font("Segoe UI Semibold", 39, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(240, 234, 216))
$graphics.DrawString("P", $font, $brush, 12, 5)
$graphics.DrawLines($mint, @(
    (New-Object System.Drawing.Point(36, 43)),
    (New-Object System.Drawing.Point(43, 36)),
    (New-Object System.Drawing.Point(49, 40)),
    (New-Object System.Drawing.Point(58, 27))
))

$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$iconStream = [System.IO.File]::Create($iconPath)
$icon.Save($iconStream)
$iconStream.Dispose()
$icon.Dispose()
$graphics.Dispose()
$bitmap.Dispose()
$gold.Dispose()
$mint.Dispose()
$font.Dispose()
$brush.Dispose()

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $env:SystemRoot "System32\wscript.exe"
$shortcut.Arguments = "`"$launcher`""
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "Open the PACBOT trading dashboard"
$shortcut.Save()

Write-Host "Desktop shortcut created: $shortcutPath"
Write-Host "Double-click PACBOT to start the app."