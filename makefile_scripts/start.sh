#!/bin/bash
# if [[ -z $(docker volume ls -f name=${DATABASE_VOL} --format="{{ .Name }}") ]]; then
# 	echo "Creating Database volume"
# 	docker volume create ${DATABASE_VOL}
# fi

LAUNCHER_ID=$(grep LAUNCHER_ID $HOME/.splight/launcher_config) && LAUNCHER_ID=${LAUNCHER_ID//*LAUNCHER_ID: /}

if [[ -z "$LAUNCHER_ID" ]]; then
    printf "Enter a name for your launcher (e.g. 'my-launcher'): "
    read -r LAUNCHER_NAME
    echo "LAUNCHER_NAME: $LAUNCHER_NAME"
    echo "Starting launcher with name: $LAUNCHER_NAME"
fi

LAUNCHER_NAME=$LAUNCHER_NAME docker compose -f docker-compose.yml up -d
