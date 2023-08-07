#!/bin/bash
# if [[ -z $(docker volume ls -f name=${DATABASE_VOL} --format="{{ .Name }}") ]]; then
# 	echo "Creating Database volume"
# 	docker volume create ${DATABASE_VOL}
# fi

AGENT_ID=$(grep AGENT_ID $HOME/.splight/agent_config) && AGENT_ID=${AGENT_ID//*AGENT_ID: /}

if [[ -z "$AGENT_ID" ]]; then
    printf "Enter a name for your agent (e.g. 'my-agent'): "
    read -r AGENT_NAME
    echo "AGENT_NAME: $AGENT_NAME"
    echo "Starting agent with name: $AGENT_NAME"
fi

AGENT_NAME=$AGENT_NAME docker compose -f docker-compose.yml up -d
