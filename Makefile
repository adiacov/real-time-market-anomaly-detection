
# Start docker containers, networks
d-up:
	docker compose up

# Start docker containers, networks in detached mode
d-upd:
	docker compse up -d

# Stop and remove docker containers, networks
d-down:
	docker compose down

# Stop and remove docker containers, networks. Remove named volumes.
d-down-clean:
	docker compose down --volumes
