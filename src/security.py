from functools import wraps
# from app import app

import datetime
import jwt
# from model import History
import logging
import json
import config

idrsa = config.KC_PUBLIC_KEY
options = config.JWT_OPTIONS
public_key = f"-----BEGIN PUBLIC KEY-----\n {idrsa} \n-----END PUBLIC KEY-----"


def extract_items(token, name):
	n = token.get(name, [])
	return [s.replace("/", "") for s in n]


#decoded = jwt.decode(token, public_key2, audience={'aud' : 'myapp'} ,algorithms='RS256', options=options)
def login_required(f):
	"""Docorator for function expecting header 'Authorization: Bearer <token>'"""
	@wraps(f)
	async def decorated_function(request, *args, **kwargs):
		token = request.headers['Authorization']
		token = (token.split('Bearer')[-1] if 'Bearer' in token else token).strip()
		groups = []

		try:
			decoded = jwt.decode(token, public_key, algorithms='RS256', options=options)
			groups = [s.replace("/","") for s in decoded.get('group', groups)]
		except Exception as e:
				raise RuntimeError(f"Something went wrong: {str(e)}")
		
		userid = decoded.get('preferred_username')
		groups = extract_items(decoded, 'group')
		projects = extract_items(decoded, 'group_projects')

		groups = ['no_groups'] if len(groups) == 0 else groups
		projects = ['no_projects'] if len(projects) == 0 else projects

		timestamp = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")

		print(timestamp + "\t" + userid + "\t" + ",".join(groups) + "\t" + str(request.url) + "-" + request.method)
		return await f(userid=userid, groups=groups, projects=projects, *args, **kwargs)
	return decorated_function


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