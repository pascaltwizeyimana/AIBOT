try {
    $ErrorActionPreference = "Stop"
    $startupStage = "Checking installation"

    $projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    $python = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $frontend = Join-Path $projectRoot "frontend"
    $vite = Join-Path $frontend "node_modules\vite\bin\vite.js"
    $apiUrl = "http://127.0.0.1:8000/api/v1/health"
    $appUrl = "http://127.0.0.1:5173"
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue

    function Test-HttpEndpoint([string]$Url) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing
            return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
        }
        catch {
            return $false
        }
    }

    if (-not (Test-Path $python)) {
        throw "Python environment not found. Follow the Windows install steps in README.md first."
    }
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        throw "Frontend dependencies are missing. Run 'npm install' from the frontend folder first."
    }
    if (-not $nodeCommand -or -not (Test-Path $vite)) {
        throw "Node.js or the Vite launcher is missing. Install Node.js LTS and run 'npm install' in the frontend folder."
    }

    if (-not (Test-HttpEndpoint $apiUrl)) {
        $startupStage = "Starting the local API"
        Start-Process -FilePath $python `
            -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000" `
            -WorkingDirectory $projectRoot -WindowStyle Hidden
    }

    if (-not (Test-HttpEndpoint $appUrl)) {
        $startupStage = "Starting the PACBOT dashboard"
        Start-Process -FilePath $nodeCommand.Source `
            -ArgumentList "`"$vite`" --host 127.0.0.1 --port 5173" `
            -WorkingDirectory $frontend -WindowStyle Hidden
    }

    $startupStage = "Waiting for PACBOT services"
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if ((Test-HttpEndpoint $apiUrl) -and (Test-HttpEndpoint $appUrl)) {
            break
        }
        Start-Sleep -Seconds 2
    }

    if (-not (Test-HttpEndpoint $apiUrl) -or -not (Test-HttpEndpoint $appUrl)) {
        throw "PACBOT services did not become ready within 60 seconds. Verify MT5/API setup and frontend dependencies."
    }

    $startupStage = "Opening the PACBOT app window"
    $edgePaths = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe")
    ) | Where-Object { $_ -and (Test-Path $_) }

    if ($edgePaths.Count -gt 0) {
        Start-Process -FilePath $edgePaths[0] -ArgumentList "--app=$appUrl"
    }
    else {
        Start-Process $appUrl
    }
}
catch {
    $shell = New-Object -ComObject WScript.Shell
    $message = "PACBOT could not start while $startupStage.`n`n$($_.Exception.Message)"
    $null = $shell.Popup($message, 0, "PACBOT could not start", 16)
}