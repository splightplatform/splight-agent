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

wait_for_docker() {
    local timeout=30
    local counter=0
    local docker_status
    while [ "$counter" -lt "$timeout" ]; do
        docker_status=$(docker info > /dev/null 2>&1 && echo "ok" || echo "error")
        if [ "$docker_status" = "ok" ]; then
            return 0
        fi
        echo "Attempt ${counter}. Waiting 5 seconds to retry"
        sleep 5
        counter=$((counter + 1))
    done
    return 1
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
AGENT_VERSION="0.5.4"
RESTART_POLICY="unless-stopped"
LOG_LEVEL=10


while getopts t: flag
do
  case "${flag}" in
    t) TOKEN="${OPTARG}";;
  esac
done


# Wait for docker to start
wait_for_docker
if [ $? -eq 1 ]; then
    print_message "Could not connect to Docker. Is Docker running?"
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

PROC_PATH=$(mount -t proc | egrep -o '/[^ ]+')
REPORT_USAGE=false
if [ -d "$PROC_PATH" ]; then
    REPORT_USAGE=true
else
    print_message "WARNING: OS does not support procfs. Usage metrics will not be reported."
fi


# Pull the Docker image
print_message "Pulling Docker image..."
docker pull "$DOCKER_IMAGE"

# Run the container
print_message "Running container..."

# Create env variables from config file needed for the splight runner
while IFS=: read -r key value; do
  export "$key"="${value// /}"
done < $CONFIG_FILE
docker run \
      --privileged \
      -id \
      --name $CONTAINER \
      -v $SPLIGHT_HOME:/root/.splight \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -e LOG_LEVEL=$LOG_LEVEL \
      -e COMPUTE_NODE_ID=$COMPUTE_NODE_ID \
      -e SPLIGHT_ACCESS_ID=$SPLIGHT_ACCESS_ID \
      -e SPLIGHT_GRPC_HOST=$SPLIGHT_GRPC_HOST \
      -e SPLIGHT_PLATFORM_API_HOST=$SPLIGHT_PLATFORM_API_HOST \
      -e SPLIGHT_SECRET_KEY=$SPLIGHT_SECRET_KEY \
      -e PROCESS_TYPE=agent \
      -e REPORT_USAGE=$REPORT_USAGE \
      --restart $RESTART_POLICY \
      $DOCKER_IMAGE

print_message "Splight agent started successfully."
