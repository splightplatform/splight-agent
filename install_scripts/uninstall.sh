set -e

print_colored_message() {
    local message="$1"
    
    printf "%s\n" "${message}"
}

print_colored_message "Uninstalling Splight agent"

docker stop splight-agent --time 600
docker rm splight-agent

print_colored_message "Splight agent uninstalled successfully."