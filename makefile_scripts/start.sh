#!/bin/bash
# if [[ -z $(docker volume ls -f name=${DATABASE_VOL} --format="{{ .Name }}") ]]; then
# 	echo "Creating Database volume"
# 	docker volume create ${DATABASE_VOL}
# fi

if [[ -z $(ls config/.env) ]]; then
	echo "Creating env"
	cp config/.env.template config/.env
fi

docker compose -f docker-compose.yml up -d
