#!/bin/bash

set -e

# Colors for prompts
BLUE=$(tput setaf 4)
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
NORMAL=$(tput sgr0)

print_colored_message() {
    local color="$1"
    local message="$2"
    
    printf "%s\n" "${color}${message}${NORMAL}"
}

handle_error() {   
    local error_code="$1"

    print_colored_message "$RED" "An error ocurred. Exiting."
    exit "$error_code"
}

trap 'handle_error $?' ERR

ART_LOGO="                                                                                                                                                         
                                                                                          
                                                                                          
                 ..                        .-:                                            
             =%@@@@@%*-               %@@  +@@-              %@@          =**.            
            %@@+.  -@@@- ---.:-=-:    %@@  .--.   :-==: ---  %@@ -==-.   -%@@+-.          
            #@@#-:       @@@@@@@@@#   %@@  +@@-  %@@@@@%@@%  %@@%@@@@@+  @@@@@@-          
             =%@@@@%*=   @@@%.  +@@%  %@@  +@@- *@@*  .%@@%  %@@=  .%@@.  #@@:            
                :-+%@@@: @@@=    %@@. %@@  +@@- %@@:   .@@%  %@@    +@@-  #@@:            
           .%%#:   :@@@= @@@#   -@@@  %@@  +@@- *@@*. :#@@%  %@@    +@@-  #@@=            
            :%@@@@@@@@+  @@@@@@@@@#   %@@  +@@-  *@@@@@*@@%  %@@    +@@-  =@@@@-          
              :-=+=-:    @@@=:-=-:    ---  .--.  .--:: :@@%  ---    .--.    -==.          
                         @@@=                   :@@@**#@@@=                               
                         +**:                       ***                                 
                                                                                          
                                                                                                                                     
                                        
"

print_colored_message "$GREEN" "$ART_LOGO"

# -----------------------------------------------

CONFIG_FILE=$HOME/.splight/agent_config
CONTAINER="splight-agent"
AGENT_VERSION="0.2.4"
RESTART_POLICY="unless-stopped"
LOG_LEVEL=10


while getopts t: flag
do
  case "${flag}" in
    t) TOKEN="${OPTARG}";;
  esac
done

# check if docker is installed
if ! [ -x "$(command -v docker)" ]; then
    print_colored_message "$RED" "Docker is not installed. Please install Docker first."
    exit 1
fi


DOCKER_IMAGE="public.ecr.aws/h2s4s1p9/splight-agent:$AGENT_VERSION"

if [ ! -f "$CONFIG_FILE" ]; then
    touch "$CONFIG_FILE"
    print_colored_message "$GREEN" "Config file created."
fi

COMPUTE_NODE_ID=$(grep COMPUTE_NODE_ID $CONFIG_FILE) && COMPUTE_NODE_ID=${COMPUTE_NODE_ID//*COMPUTE_NODE_ID: /}

if [ -z "$TOKEN" ]; then
    if [ -z "$COMPUTE_NODE_ID" ]; then
        read -p "Enter agent TOKEN: " TOKEN
        echo $TOKEN | base64 --decode > $CONFIG_FILE
    fi
else
    echo $TOKEN | base64 --decode > $CONFIG_FILE
fi


# Pull the Docker image
print_colored_message "$GREEN" "Pulling Docker image..."
docker pull "$DOCKER_IMAGE"

# Run the container
print_colored_message "$GREEN" "Running container..."
docker run \
      --privileged \
      -id \
      --name $CONTAINER \
      -v $CONFIG_FILE:/root/.splight/agent_config \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -e LOG_LEVEL=$LOG_LEVEL \
      --restart $RESTART_POLICY \
      $DOCKER_IMAGE

print_colored_message "$GREEN" "Splight agent started successfully."
