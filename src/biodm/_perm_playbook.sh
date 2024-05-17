curl -d '{"username": "titi"}' http://127.0.0.1:8000/users/
curl -d '{"name": "", "users":[{"username": ""}]}' http://127.0.0.1:8000/groups/

curl http://127.0.0.1:8000/login
http://keycloak.local:8080/realms/3TR/protocol/openid-connect/auth?client_id=submission_client&response_type=code&redirect_uri=http://127.0.0.1:8000/syn_ack&scope=openid&state=

curl -d '{"name": "ds_test3", "contact": {"username": "toto"}, "tags": [{"name":"bip"}, {"name":"bap"}, {"name":"bop"}]}' http://127.0.0.1:8000/datasets/ -H "Authorization: Bearer <token>"