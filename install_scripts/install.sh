#!/bin/bash

set -e


print_message() {
    local message="$1"
    
    printf "%s\n" "${message}"
}

handle_error() {   
    local error_code="$1"

    print_message "An error ocurred. Exiting."
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

print_message "$ART_LOGO"

# -----------------------------------------------

SPLIGHT_HOME=$HOME/.splight
CONFIG_FILE=$SPLIGHT_HOME/agent_config
CONTAINER="splight-agent"
AGENT_VERSION="0.2.11"
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
    print_message "Docker is not installed. Please install Docker first."
    exit 1
fi


DOCKER_IMAGE="public.ecr.aws/h2s4s1p9/splight-agent:$AGENT_VERSION"

if [ ! -f "$CONFIG_FILE" ]; then
    mkdir -p $SPLIGHT_HOME && touch "$CONFIG_FILE"
    print_message "Config file created."
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
print_message "Pulling Docker image..."
docker pull "$DOCKER_IMAGE"

# Run the container
print_message "Running container..."
docker run \
      --privileged \
      -id \
      --name $CONTAINER \
      -v $SPLIGHT_HOME:/root/.splight \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -e LOG_LEVEL=$LOG_LEVEL \
      --restart $RESTART_POLICY \
      $DOCKER_IMAGE

print_message "Splight agent started successfully."
