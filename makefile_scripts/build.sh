#!/bin/bash
if [[ -z $(ls config/.env) ]]; then
	echo "Creating env"
	cp config/.env.template config/.env
fi

docker compose -f docker-compose.yml build splight-launcher