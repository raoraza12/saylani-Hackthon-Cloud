param(
    [int]$Port = 8080,
    [string]$Root = $PSScriptRoot
)

$listener = New-Object System.Net.HttpListener
$prefix = "http://localhost:$Port/"
$listener.Prefixes.Add($prefix)

try {
    $listener.Start()
    Write-Host "================================================="
    Write-Host " Local Web Server Started Successfully!"
    Write-Host " Open in Browser: $prefix"
    Write-Host " Root Directory : $Root"
    Write-Host "================================================="
} catch {
    Write-Error "Could not start server on port $Port : $_"
    exit 1
}

$mimeTypes = @{
    ".html" = "text/html; charset=utf-8"
    ".htm"  = "text/html; charset=utf-8"
    ".css"  = "text/css; charset=utf-8"
    ".js"   = "application/javascript; charset=utf-8"
    ".json" = "application/json; charset=utf-8"
    ".csv"  = "text/csv; charset=utf-8"
    ".png"  = "image/png"
    ".jpg"  = "image/jpeg"
    ".jpeg" = "image/jpeg"
    ".svg"  = "image/svg+xml"
    ".ico"  = "image/x-icon"
}

while ($listener.IsListening) {
    try {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response

        $rawUrl = $request.Url.LocalPath.TrimStart('/')
        if ([string]::IsNullOrWhiteSpace($rawUrl) -or $rawUrl -eq "index.html" -or $rawUrl -eq "cfo" -or $rawUrl -eq "dashboard") {
            $rawUrl = "presentation/cfo_dashboard.html"
        }

        # Decode URL
        $relativePath = [System.Uri]::UnescapeDataString($rawUrl).Replace('/', '\')
        $filePath = Join-Path $Root $relativePath

        # Fallback check under presentation subfolder
        if (-not (Test-Path -Path $filePath -PathType Leaf)) {
            $subPath = Join-Path (Join-Path $Root "presentation") $relativePath
            if (Test-Path -Path $subPath -PathType Leaf) {
                $filePath = $subPath
            }
        }

        if (Test-Path -Path $filePath -PathType Leaf) {
            $ext = [System.IO.Path]::GetExtension($filePath).ToLower()
            $mime = if ($mimeTypes.ContainsKey($ext)) { $mimeTypes[$ext] } else { "application/octet-stream" }
            $response.ContentType = $mime

            $bytes = [System.IO.File]::ReadAllBytes($filePath)
            $response.ContentLength64 = $bytes.Length
            $response.OutputStream.Write($bytes, 0, $bytes.Length)
            $response.StatusCode = 200
        } else {
            $response.StatusCode = 404
            $msg = [System.Text.Encoding]::UTF8.GetBytes("<h1>404 Not Found</h1><p>File $relativePath was not found.</p>")
            $response.ContentType = "text/html"
            $response.ContentLength64 = $msg.Length
            $response.OutputStream.Write($msg, 0, $msg.Length)
        }
        $response.Close()
    } catch {
        # continue listening on errors
    }
}
