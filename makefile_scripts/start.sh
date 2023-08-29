CONFIG_FILE=$HOME/.splight/agent_config
if [ ! -f "$CONFIG_FILE" ]; then
    touch $CONFIG_FILE
fi

if [ -n "$TOKEN" ]; then
    echo $TOKEN | base64 --decode > $CONFIG_FILE
fi

COMPUTE_NODE_ID=$(grep COMPUTE_NODE_ID $CONFIG_FILE) && COMPUTE_NODE_ID=${COMPUTE_NODE_ID//*COMPUTE_NODE_ID: /}

if [ -z "$COMPUTE_NODE_ID" ]; then
    if [ ! -n "$TOKEN" ]; then
        printf "You need to set the TOKEN variable\n"
        exit 1
    fi
fi

docker compose -f docker-compose.yml up -d
