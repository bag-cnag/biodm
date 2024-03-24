#!make
SHELL := /bin/bash
KC_ADMIN_URL = https://sso.gpapdev.cnag.
LOGIN_ENDPOINT = http://127.0.0.1:8000/login
GET_LOGIN_URL = $(shell curl -s $(LOGIN_ENDPOINT))

.PHONY: venv
venv:
	python3 -m venv venv && source venv/bin/activate && pip install -r requirements-mini.txt

db-run:
	docker run --name biodm-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=biodm -d postgres:16-bookworm


db-ip:
	docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' biodm-pg
db-stop:
	docker stop biodm-pg
	docker rm biodm-pg

run:
	python3 src/app.py

stop:
	fuser -k 5000/tcp

kc-admin:
	carbonyl "$(KC_ADMIN)"

manual-login:
	@echo "LOGIN URL:"
	@echo "$(GET_LOGIN_URL)"
	carbonyl "$(GET_LOGIN_URL)"

automated-login:
	python3 automated_login.py
	@echo "-----------"
	@echo "token saved in kc.env file"
