#!/bin/bash

# Debug script for Squeezelite volume control
BASE_URL="https://players.home.chrisuthe.com"

echo "🔍 Testing Squeezelite API endpoints..."
echo "======================================"

echo
echo "1. Testing debug endpoint:"
echo "curl $BASE_URL/api/debug/audio"
curl -s "$BASE_URL/api/debug/audio" | jq '.' 2>/dev/null || curl -s "$BASE_URL/api/debug/audio"

echo
echo "2. Getting players list:"
echo "curl $BASE_URL/api/players"
PLAYERS_RESPONSE=$(curl -s "$BASE_URL/api/players")
echo "$PLAYERS_RESPONSE" | jq '.' 2>/dev/null || echo "$PLAYERS_RESPONSE"

echo
echo "3. Getting available devices:"
echo "curl $BASE_URL/api/devices"
curl -s "$BASE_URL/api/devices" | jq '.' 2>/dev/null || curl -s "$BASE_URL/api/devices"

echo
echo "4. Extract player names and test volume control:"
# Try to extract player names from the response
PLAYER_NAMES=$(echo "$PLAYERS_RESPONSE" | jq -r '.players | keys[]' 2>/dev/null)

if [ -n "$PLAYER_NAMES" ]; then
    for player in $PLAYER_NAMES; do
        echo
        echo "Testing player: $player"
        echo "--------------------"
        
        echo "Getting current volume:"
        echo "curl $BASE_URL/api/players/$player/volume"
        VOLUME_RESPONSE=$(curl -s "$BASE_URL/api/players/$player/volume")
        echo "$VOLUME_RESPONSE" | jq '.' 2>/dev/null || echo "$VOLUME_RESPONSE"
        
        echo
        echo "Testing volume set to 75%:"
        echo "curl -X POST $BASE_URL/api/players/$player/volume -H 'Content-Type: application/json' -d '{\"volume\": 75}'"
        SET_RESPONSE=$(curl -s -X POST "$BASE_URL/api/players/$player/volume" \
            -H "Content-Type: application/json" \
            -d '{"volume": 75}')
        echo "$SET_RESPONSE" | jq '.' 2>/dev/null || echo "$SET_RESPONSE"
        
        echo "----------------------------------------"
    done
else
    echo "No players found or could not parse player names."
    echo "You can manually test with a player name like this:"
    echo "curl $BASE_URL/api/players/YOUR_PLAYER_NAME/volume"
    echo "curl -X POST $BASE_URL/api/players/YOUR_PLAYER_NAME/volume -H 'Content-Type: application/json' -d '{\"volume\": 50}'"
fi

echo
echo "🏁 Debug test complete!"
echo "If you see 'Unexpected token <' errors, it means the server is returning HTML instead of JSON."
echo "If you see JSON responses, the API is working correctly."