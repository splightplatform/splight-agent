set -e

print_message() {
    local message="$1"
    
    printf "%s\n" "${message}"
}

print_message "Uninstalling Splight agent"

docker stop splight-agent --time 600
docker rm splight-agent

print_message "Note: agent configuration at ~/.splight/agent_config was kept."
print_message "Delete it before installing a DIFFERENT agent on this machine, or pass -t <token> to install.sh."

print_message "Splight agent uninstalled successfully."