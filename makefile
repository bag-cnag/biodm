#!make
SHELL := /bin/bash

.PHONY: venv
venv:
	python3 -m venv venv && source venv/bin/activate && pip install -r requirements-mini.txt

db-run:
	docker run --name biodm-pg -e POSTGRES_PASSWORD=pass -d postgres:16-bookworm

db-ip:
	docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' biodm-pg

run:
	python3 src/app.py