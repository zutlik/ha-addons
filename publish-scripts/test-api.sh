# =============================================================================
# HEALTH ROUTER ENDPOINTS
# =============================================================================

# Root endpoint - Get basic app information
curl -X GET "http://localhost:8099/" | jq

# Health check endpoint
curl -X GET "http://localhost:8099/health" | jq

# =============================================================================
# SCRIPTS ROUTER ENDPOINTS
# =============================================================================

# Get all available scripts from Home Assistant
curl -X GET "http://localhost:8099/scripts/" | jq

# Get information about a specific script
curl -X GET "http://localhost:8099/scripts/script.yuval_phone_notification_test_script" | jq

# Execute a script (requires active tunnel)
curl -X GET "http://localhost:8099/scripts/run/script.yuval_phone_notification_test_script" | jq

# =============================================================================
# TUNNELS ROUTER ENDPOINTS
# =============================================================================

# Create a new tunnel for a script
curl -X POST "http://localhost:8099/tunnels/create" \
  -H "Content-Type: application/json" \
  -d '{
    "script_id": "script.yuval_phone_notification_test_script" | jq
  }'

# Get all active tunnels
curl -X GET "http://localhost:8099/tunnels/" | jq

# Get information about a specific tunnel
curl -X GET "http://localhost:8099/tunnels/script.your_script_name" | jq

# Delete a specific tunnel
curl -X DELETE "http://localhost:8099/tunnels/script.your_script_name" | jq

# Delete all tunnels
curl -X DELETE "http://localhost:8099/tunnels/" | jq

# =============================================================================
# DEBUG ROUTER ENDPOINTS
# =============================================================================

# Get debug information about paths and files
curl -X GET "http://localhost:8099/debug-paths" | jq

# =============================================================================
# COMPLETE WORKFLOW EXAMPLE
# =============================================================================

# 1. Check if the app is running
curl -X GET "http://localhost:8099/" | jq

# 2. Check health status
curl -X GET "http://localhost:8099/health" | jq

# 3. Get available scripts
curl -X GET "http://localhost:8099/scripts/" | jq

# 4. Create a tunnel for a specific script (replace with actual script ID)
curl -X POST "http://localhost:8099/tunnels/create" \
  -H "Content-Type: application/json" \
  -d '{
    "script_id": "script.turn_on_living_room_lights" | jq
  }'

# 5. Check active tunnels
curl -X GET "http://localhost:8099/tunnels/" | jq

# 6. Execute the script via the tunnel
curl -X GET "http://localhost:8099/scripts/run/script.turn_on_living_room_lights" | jq

# 7. Get debug information
curl -X GET "http://localhost:8099/debug-paths" | jq

# 8. Clean up - delete the tunnel
curl -X DELETE "http://localhost:8099/tunnels/script.turn_on_living_room_lights" | jq

# =============================================================================
# WITH JQ FORMATTING (if you have jq installed)
# =============================================================================

# Pretty print all responses
curl -s -X GET "http://localhost:8099/" | jq '.'
curl -s -X GET "http://localhost:8099/health" | jq '.'
curl -s -X GET "http://localhost:8099/scripts/" | jq '.'
curl -s -X GET "http://localhost:8099/tunnels/" | jq '.'
curl -s -X GET "http://localhost:8099/debug-paths" | jq '.'

# Extract specific fields
curl -s -X GET "http://localhost:8099/tunnels/" | jq '.tunnels[0].tunnel_url'
curl -s -X GET "http://localhost:8099/scripts/" | jq '.scripts[0].entity_id'
curl -s -X GET "http://localhost:8099/health" | jq '.ha_connected'

# =============================================================================
# ERROR HANDLING EXAMPLES
# =============================================================================

# Test with invalid script ID
curl -X GET "http://localhost:8099/scripts/invalid_script_id" | jq

# Test tunnel creation with non-existent script
curl -X POST "http://localhost:8099/tunnels/create" \
  -H "Content-Type: application/json" \
  -d '{
    "script_id": "script.non_existent_script" | jq
  }'

# Test script execution without tunnel
curl -X GET "http://localhost:8099/scripts/run/script.your_script_name" | jq

# =============================================================================
# ENVIRONMENT-SPECIFIC COMMANDS
# =============================================================================

# For Docker container (if running on different port)
curl -X GET "http://your-container-ip:8099/" | jq

# For Home Assistant add-on (if running in HA)
curl -X GET "http://your-ha-ip:8099/" | jq

# With authentication (if needed)
curl -X GET "http://localhost:8099/" \
  -H "Authorization: Bearer your-token" | jq

# =============================================================================
# BATCH TESTING
# =============================================================================

# Test all GET endpoints
for endpoint in "/" "/health" "/scripts/" "/tunnels/" "/debug-paths"; do
  echo "Testing $endpoint" | jq
  curl -s -X GET "http://localhost:8099$endpoint" | jq '.'
  echo "---" | jq
done

# Test tunnel lifecycle
echo "Creating tunnel..." | jq
curl -s -X POST "http://localhost:8099/tunnels/create" \
  -H "Content-Type: application/json" \
  -d '{"script_id": "script.test_script"}' | jq '.'

echo "Listing tunnels..." | jq
curl -s -X GET "http://localhost:8099/tunnels/" | jq '.'

echo "Deleting tunnel..." | jq
curl -s -X DELETE "http://localhost:8099/tunnels/script.test_script" | jq '.'