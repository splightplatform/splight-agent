BLUE=$(tput setaf 4)
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
NORMAL=$(tput sgr0)

print_colored_message() {
    local color="$1"
    local message="$2"
    
    printf "%s\n" "${color}${message}${NORMAL}"
}

docker stop splight-agent
docker rm splight-agent

print_colored_message "$GREEN" "Splight agent uninstalled successfully."