#!/bin/bash

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
RESTART_POLICY="unless-stopped"
LOG_LEVEL=10


while getopts t:v: flag
do
  case "${flag}" in
    t) TOKEN="${OPTARG}";;
    v) AGENT_VERSION="${OPTARG}";;
  esac
done

# check if docker is installed
if ! [ -x "$(command -v docker)" ]; then
    print_colored_message "$RED" "Docker is not installed. Please install Docker first."
    exit 1
fi

# check if AGENT_VERSION is set
if [ -z "$AGENT_VERSION" ]; then
    print_colored_message "$RED" "AGENT_VERSION is not set. Please set AGENT_VERSION."
    exit 1
fi

DOCKER_IMAGE="public.ecr.aws/h2s4s1p9/splight-agent:$AGENT_VERSION"

if [ ! -f "$CONFIG_FILE" ]; then
    touch "$CONFIG_FILE"
    print_colored_message "$GREEN" "Config file created."
fi

COMPUTE_NODE_ID=$(grep COMPUTE_NODE_ID $CONFIG_FILE) && COMPUTE_NODE_ID=${COMPUTE_NODE_ID//*COMPUTE_NODE_ID: /}

if [ -z "$COMPUTE_NODE_ID" ]; then
    # Check if TOKEN argument is provided, or prompt for input
    if [ -z "$TOKEN" ]; then
        read -p "Enter agent TOKEN: " TOKEN
    fi
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
      --mount source=$CONFIG_FILE,target=/root/.splight/agent_config \
      --mount source=/var/run/docker.sock,target=/var/run/docker.sock \
      -e LOG_LEVEL=$LOG_LEVEL \
      --restart $RESTART_POLICY \
      $DOCKER_IMAGE

print_colored_message "$GREEN" "Splight agent started successfully."
