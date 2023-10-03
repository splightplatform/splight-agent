set -e

print_message() {
    local message="$1"
    
    printf "%s\n" "${message}"
}

print_message "Uninstalling Splight agent"

docker stop splight-agent --time 600
docker rm splight-agent

print_message "Splight agent uninstalled successfully."