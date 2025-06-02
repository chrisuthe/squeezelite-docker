#!/bin/bash

# Quick debugging script for container startup issues

echo "Squeezelite Container Debug Script"
echo "=================================="

# Basic container info
echo "1. Container Status:"
docker-compose ps

echo -e "\n2. Recent Container Logs:"
docker-compose logs --tail=20 squeezelite-multiroom

echo -e "\n3. Checking if container is running:"
if docker-compose exec squeezelite-multiroom echo "Container is accessible" 2>/dev/null; then
    echo "✓ Container is running and accessible"
    
    echo -e "\n4. Supervisor Status:"
    docker-compose exec squeezelite-multiroom supervisorctl status
    
    echo -e "\n5. Process List:"
    docker-compose exec squeezelite-multiroom ps aux
    
    echo -e "\n6. Application Logs:"
    echo "--- Web Output Log ---"
    docker-compose exec squeezelite-multiroom tail -n 10 /app/logs/web-output.log 2>/dev/null || echo "No web output log yet"
    
    echo -e "\n--- Web Error Log ---"
    docker-compose exec squeezelite-multiroom tail -n 10 /app/logs/web-error.log 2>/dev/null || echo "No web error log yet"
    
    echo -e "\n--- Application Log ---"
    docker-compose exec squeezelite-multiroom tail -n 10 /app/logs/application.log 2>/dev/null || echo "No application log yet"
    
    echo -e "\n7. Manual App Test:"
    echo "Testing Flask app manually..."
    docker-compose exec squeezelite-multiroom timeout 5 python3 /app/app.py || echo "Manual app test failed or timed out"
    
    echo -e "\n8. Health Check:"
    docker-compose exec squeezelite-multiroom python3 /app/health_check.py
    
    echo -e "\n9. Port Check:"
    docker-compose exec squeezelite-multiroom netstat -tlnp | grep 8080 || echo "Port 8080 not in use inside container"
    
else
    echo "✗ Container is not running or not accessible"
    echo "Try: docker-compose up -d"
fi

echo -e "\n10. Host Port Check:"
netstat -tlnp 2>/dev/null | grep 8080 || ss -tlnp 2>/dev/null | grep 8080 || echo "Port 8080 not in use on host"

echo -e "\nIf issues persist:"
echo "1. Check detailed logs with: docker-compose logs -f"
echo "2. Get shell access with: docker-compose exec squeezelite-multiroom /bin/bash"
echo "3. Restart container with: docker-compose restart"
echo "4. Rebuild if needed with: docker-compose build --no-cache"
