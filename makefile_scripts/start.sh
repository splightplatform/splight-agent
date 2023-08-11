#!/bin/bash
# if [[ -z $(docker volume ls -f name=${DATABASE_VOL} --format="{{ .Name }}") ]]; then
# 	echo "Creating Database volume"
# 	docker volume create ${DATABASE_VOL}
# fi

AGENT_ID=$(grep AGENT_ID $HOME/.splight/agent_config) && AGENT_ID=${AGENT_ID//*AGENT_ID: /}

if [[ -z "$AGENT_ID" ]]; then
    printf "Enter the compute node's id: "
    read -r AGENT_ID
    echo "Starting agent with id: $AGENT_ID"
fi

AGENT_ID=$AGENT_ID docker compose -f docker-compose.yml up -d
