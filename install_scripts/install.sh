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
AGENT_VERSION="0.10.1"
RESTART_POLICY="unless-stopped"
LOG_LEVEL=10
STOP_TIMEOUT=600
REQUIRED_CONFIG_KEYS="COMPUTE_NODE_ID SPLIGHT_ACCESS_ID SPLIGHT_SECRET_KEY"


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

# Decode a base64 token into a staging file inside SPLIGHT_HOME and validate
# it. The staging file lives on the same filesystem as CONFIG_FILE so the
# later mv is atomic. The existing config is left untouched here: it is only
# committed once the old container has been stopped.
prepare_token() {
    local token="$1"
    STAGED_CONFIG=$(mktemp "$SPLIGHT_HOME/.agent_config.XXXXXX")
    if [ -z "$token" ] || ! printf '%s' "$token" | base64 --decode > "$STAGED_CONFIG" 2>/dev/null; then
        rm -f "$STAGED_CONFIG"
        print_message "Invalid token: could not decode agent configuration."
        exit 1
    fi
    local required_key
    for required_key in $REQUIRED_CONFIG_KEYS; do
        if ! grep -q "^[[:space:]]*${required_key}:" "$STAGED_CONFIG"; then
            rm -f "$STAGED_CONFIG"
            print_message "Invalid token: missing ${required_key} in agent configuration."
            exit 1
        fi
    done
}

mkdir -p "$SPLIGHT_HOME"
[ -f "$CONFIG_FILE" ] || touch "$CONFIG_FILE"

# Acquire a token when needed. SPLIGHT_PLATFORM_API_HOST is intentionally not
# required: the agent ships with a built-in default.
STAGED_CONFIG=""
if [ -n "$TOKEN" ]; then
    prepare_token "$TOKEN"
elif ! grep -q "^[[:space:]]*COMPUTE_NODE_ID:" "$CONFIG_FILE"; then
    if ! read -r -p "Enter agent TOKEN: " TOKEN || [ -z "$TOKEN" ]; then
        print_message "A token is required to install the agent. Re-run with: ./install.sh -t <token>"
        exit 1
    fi
    prepare_token "$TOKEN"
else
    print_message "Reusing existing agent identity from $CONFIG_FILE."
    print_message "If you intended to install a NEW agent, re-run with: ./install.sh -t <token>"
fi

# Read identity from the staged file when a token was supplied, otherwise from
# the existing config.
CONFIG_SOURCE="${STAGED_CONFIG:-$CONFIG_FILE}"

# Clear any identity values leaked in from the caller's shell so the config is
# the only source of truth.
unset COMPUTE_NODE_ID SPLIGHT_ACCESS_ID SPLIGHT_SECRET_KEY SPLIGHT_PLATFORM_API_HOST

# `|| [ -n "$key" ]` processes the final line even without a trailing newline.
# Keys are trimmed of surrounding whitespace so indented lines are honoured.
# Lines whose key holds anything but A-Z, a-z, 0-9 or underscore are skipped.
# Carriage returns are stripped to tolerate CRLF tokens.
while IFS=: read -r key value || [ -n "$key" ]; do
  key="${key#"${key%%[![:space:]]*}"}"
  key="${key%"${key##*[![:space:]]}"}"
  case "$key" in
    "" ) continue ;;
    *[!A-Za-z0-9_]* ) continue ;;
  esac
  value="${value//$'\r'/}"
  export "$key"="${value// /}"
done < "$CONFIG_SOURCE"

for required_var in $REQUIRED_CONFIG_KEYS; do
    if [ -z "${!required_var}" ]; then
        print_message "Configuration error: ${required_var} is missing. Aborting."
        exit 1
    fi
done

PROC_PATH=$(mount -t proc | egrep -o '/[^ ]+' || echo "")
REPORT_USAGE=false
if [ -d "$PROC_PATH" ]; then
    REPORT_USAGE=true
else
    print_message "WARNING: OS does not support procfs. Usage metrics will not be reported."
fi


# Pull the Docker image
print_message "Pulling Docker image..."
docker pull "$DOCKER_IMAGE"

# Stop and remove any pre-existing container before committing the new config.
# The old container keeps its self-consistent config until it is stopped.
if [ -n "$(docker ps -aq -f "name=^${CONTAINER}$")" ]; then
    print_message "Stopping existing '${CONTAINER}' container (up to ${STOP_TIMEOUT}s for graceful shutdown)..."
    docker stop "$CONTAINER" --time "$STOP_TIMEOUT" > /dev/null 2>&1 || true
    docker rm -f "$CONTAINER" > /dev/null
fi

if [ -n "$STAGED_CONFIG" ]; then
    mv "$STAGED_CONFIG" "$CONFIG_FILE"
    print_message "Agent configuration updated from token."
fi

# SPLIGHT_PLATFORM_API_HOST is passed only when set; an empty value would
# override the agent's built-in default.
API_HOST_ARGS=()
if [ -n "$SPLIGHT_PLATFORM_API_HOST" ]; then
    API_HOST_ARGS=(-e "SPLIGHT_PLATFORM_API_HOST=$SPLIGHT_PLATFORM_API_HOST")
fi

# Run the container
print_message "Running container..."

docker run \
      --privileged \
      -id \
      --name "$CONTAINER" \
      -v "$SPLIGHT_HOME:/root/.splight" \
      -v "/var/run/docker.sock:/var/run/docker.sock" \
      -e "LOG_LEVEL=$LOG_LEVEL" \
      -e "COMPUTE_NODE_ID=$COMPUTE_NODE_ID" \
      -e "SPLIGHT_ACCESS_ID=$SPLIGHT_ACCESS_ID" \
      "${API_HOST_ARGS[@]}" \
      -e "SPLIGHT_SECRET_KEY=$SPLIGHT_SECRET_KEY" \
      -e "PROCESS_TYPE=agent" \
      -e "REPORT_USAGE=$REPORT_USAGE" \
      --log-driver json-file \
      --log-opt max-size=10m \
      --log-opt max-file=3 \
      --restart "$RESTART_POLICY" \
      "$DOCKER_IMAGE"

print_message "Splight agent started successfully."
