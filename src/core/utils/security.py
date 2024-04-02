from typing import List
from functools import wraps, lru_cache
# from app import app

from starlette import requests


import datetime
import jwt
# from model import History
# from core.entities import History: TODO
import logging
import json
from core.exceptions import UnauthorizedError
from instance import config


def auth_header(request) -> str | None:
	return request.headers.get('Authorization', None)


@lru_cache(128)
def extract_and_decode_token(request) -> tuple[str, List, List]:
	"""Cached because it may be called twice per request: 
		1. history middleware 
		2. protected function decorator."""
	# Helper functions.
	def enclose_idrsa(idrsa) -> str:
		return f"-----BEGIN PUBLIC KEY-----\n {idrsa} \n-----END PUBLIC KEY-----"

	def extract_items(token, name, default=""):
		n = token.get(name, [])
		return [s.replace("/", "") for s in n] if n else [default]

	# Extract.
	token = auth_header(request)
	if not token:
		raise UnauthorizedError(f"This route is token protected. " 
						  		f"Please provide it in header: "
								f"Authorization: Bearer <token>")
	token = (token.split('Bearer')[-1] if 'Bearer' in token else token).strip()

	# Decode.
	try:
		decoded = jwt.decode(jwt=token,
							 key=enclose_idrsa(config.KC_PUBLIC_KEY),
							 algorithms='RS256',
							 options=config.JWT_OPTIONS)
	except Exception as e:
		raise RuntimeError(f"Something went wrong: {str(e)}")

	# Parse.
	userid = decoded.get('preferred_username')
	groups = extract_items(decoded, 'group', 'no_groups')
	projects = extract_items(decoded, 'group_projects', 'no_projects')
	return userid, groups, projects


def group_required(f, groups: List):
	"""Decorator for function expecting groups: decorates a controller CRUD function."""
	@wraps(f)
	async def wrapper(controller, request, *args, **kwargs):
		_, user_groups, _ = extract_and_decode_token(request)
		if any((ug in groups for ug in user_groups)):
			return f(controller, request, *args, **kwargs)
		raise UnauthorizedError("Insufficient group privileges for this operation.")
	return wrapper


def admin_required(f):
	return group_required(f, groups=['admin'])


def login_required(f):
	"""Docorator for function expecting header 'Authorization: Bearer <token>'"""
	@wraps(f)
	async def decorated_function(request, *args, **kwargs):
		userid, groups, projects = extract_and_decode_token(request)
		timestamp = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
		print(f'{timestamp}\t{userid}\t{",".join(groups)}\t'
			  f'{str(request.url)}-{request.method}')

		return await f(userid=userid, groups=groups, projects=projects, *args, **kwargs)
	return decorated_function


# def group_required(f, *args, **kwargs):
# 	pass


# @app.after_request
# def history(response):

# 		if request.method !="OPTIONS":

# 			if "Authorization" in request.headers:

# 				token=request.headers['Authorization']

# 				groups=[]
# 				try:
# 					decoded = jwt.decode(token, public_key,algorithms='RS256',options=options)
# 					groups=[s.replace("/","") for s in decoded.get('group')]

# 				except Exception as e:
# 					return {'message': 'Something went wrong '+str(e)}, 500

# 				userid=decoded.get('preferred_username')
# 				groups=extract_items(decoded,'group')
# 				projects=extract_items(decoded,'project')
# 				timestamp = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")

# 				splitted=request.url.split("/")
# 				entity_id=splitted[len(splitted)-1]
# 				content={'data':'empty'}
# 				updated_content = {'data':'updated'}

# 				if (request.method=="POST"):
# 					content['data']=request.json
# 					if (response.status=="200 OK" ):
# 						try:
# 							#If uploading JSON or Excel
# 							if type(response.json) == list:
# 								for ent in range(0,len(response.json)):
# 									entity_id=response.json[ent]['id']
# 									HistoryInst(entity_id, userid, groups, request, {'data':'uploaded'})
# 							#If creating manually
# 							else:
# 								entity_id=response.json['id']
# 						except Exception as e:
# 							print("POST without ID in the response")

# 				if (request.method=="PUT"):
# 					if (response.status=="200 OK" ):
# 						try:
# 							content['data']=request.json
# 						except Exception as e:
# 							print("PUT without ID in the response")
# 				#Save to db
# 				if (request.method != "GET"):
# 					HistoryInst(entity_id, userid, groups, request, content)

# 				print(timestamp+"\t"+userid+"\t"+",".join(groups)+"\t"+request.url+"-"+request.method)

# 		return response

# #Create History entry
# def HistoryInst(entity_id, userid, groups, request, content):

# 	history=History(entity_id=entity_id,
# 					timestamp=datetime.datetime.now(),
# 					username=userid,
# 					groups=",".join(groups),
# 					endpoint=request.url,
# 					method=request.method,
# 					content=content)
# 	try:
# 		history.save_to_db()

# 	except Exception as e:
# 		db.session.rollback()


# def after_this_request(func):
#     if not hasattr(g, 'call_after_request'):
#         g.call_after_request = []
#     g.call_after_request.append(func)
#     return func


# @app.after_request
# def per_request_callbacks(response):
#     for func in getattr(g, 'call_after_request', ()):
#         response = func(response)
#     return response