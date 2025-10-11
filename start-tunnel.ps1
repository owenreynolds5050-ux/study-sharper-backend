# Study Sharper LocalTunnel Startup Script
# This script creates a public tunnel to your local backend server

Write-Host "Starting LocalTunnel for Study Sharper Backend..." -ForegroundColor Green
Write-Host ""

# Configuration
$PORT = 8000
$SUBDOMAIN = "studysharper"  # You can change this to any available subdomain

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Local Port: $PORT" -ForegroundColor White
Write-Host "  Subdomain: $SUBDOMAIN" -ForegroundColor White
Write-Host ""

# Check if localtunnel is installed
try {
    $ltCheck = lt --version 2>&1
    Write-Host "LocalTunnel found: $ltCheck" -ForegroundColor Green
} catch {
    Write-Host "ERROR: LocalTunnel not found!" -ForegroundColor Red
    Write-Host "Installing LocalTunnel..." -ForegroundColor Yellow
    npm install -g localtunnel
}

Write-Host ""
Write-Host "IMPORTANT INSTRUCTIONS:" -ForegroundColor Yellow
Write-Host "1. Make sure your backend server is running on port $PORT" -ForegroundColor White
Write-Host "2. Copy the tunnel URL that appears below" -ForegroundColor White
Write-Host "3. Update BACKEND_API_URL in frontend/.env.local with the tunnel URL" -ForegroundColor White
Write-Host "4. Restart your Next.js frontend after updating the URL" -ForegroundColor White
Write-Host ""
Write-Host "Starting tunnel..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the tunnel" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================" -ForegroundColor Green

# Start LocalTunnel with subdomain
# If subdomain is taken, it will use a random one
lt --port $PORT --subdomain $SUBDOMAIN
