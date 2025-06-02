# PowerShell script to fix Docker entrypoint line ending issues
Write-Host "Fixing Docker entrypoint line ending issues..." -ForegroundColor Green
Write-Host ""

# Convert line endings from CRLF to LF
Write-Host "Converting entrypoint.sh line endings to Unix format..." -ForegroundColor Yellow
$content = Get-Content "entrypoint.sh" -Raw
$content = $content -replace "`r`n", "`n"
[System.IO.File]::WriteAllText((Resolve-Path "entrypoint.sh"), $content, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Cleaning up any existing containers and images..." -ForegroundColor Yellow
docker-compose -f docker-compose.no-audio.yml down 2>$null
docker system prune -f 2>$null

Write-Host ""
Write-Host "Rebuilding Docker image..." -ForegroundColor Yellow
docker-compose -f docker-compose.no-audio.yml build --no-cache

Write-Host ""
Write-Host "Starting container..." -ForegroundColor Yellow
docker-compose -f docker-compose.no-audio.yml up

Write-Host ""
Write-Host "Done! Your container should now start successfully." -ForegroundColor Green
