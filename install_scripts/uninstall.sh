BLUE=$(tput setaf 4)
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
NORMAL=$(tput sgr0)

set -e

print_colored_message() {
    local color="$1"
    local message="$2"
    
    printf "%s\n" "${color}${message}${NORMAL}"
}

print_colored_message "$GREEN" "Uninstalling Splight agent"

docker stop splight-agent --time 600
docker rm splight-agent

print_colored_message "$GREEN" "Splight agent uninstalled successfully."