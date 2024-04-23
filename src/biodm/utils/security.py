from datetime import datetime
from typing import List
from functools import wraps, lru_cache


from biodm.exceptions import UnauthorizedError


def auth_header(request) -> str | None:
	header = request.headers.get('Authorization')
	if not header: 
		return None
	return (header.split('Bearer')[-1] if 'Bearer' in header else header).strip()


@lru_cache(128)
async def extract_and_decode_token(kc, request) -> tuple[str, List, List]:
	"""Cached because it may be called twice per request:
	1. history middleware
	2. protected function decorator."""
	def extract_items(token, name, default=""):
		n = token.get(name, [])
		return [s.replace("/", "") for s in n] if n else [default]
	
	# Extract.
	token = auth_header(request)
	if not token:
		raise UnauthorizedError(f"This route is token protected. "
								f"Please provide it in header: "
								f"Authorization: Bearer <token>")
	decoded = await kc.decode_token(token)

	# Parse.
	userid = decoded.get('preferred_username')
	groups = extract_items(decoded, 'group', 'no_groups')
	projects = extract_items(decoded, 'group_projects', 'no_projects')
	return userid, groups, projects


def group_required(f, groups: List):
	"""Decorator for function expecting groups: decorates a controller CRUD function."""
	@wraps(f)
	async def wrapper(controller, request, *args, **kwargs):
		_, user_groups, _ = await extract_and_decode_token(controller.app.kc, request)
		if any((ug in groups for ug in user_groups)):
			return f(controller, request, *args, **kwargs)
		raise UnauthorizedError("Insufficient group privileges for this operation.")
	return wrapper


def admin_required(f):
	return group_required(f, groups=['admin'])


def login_required(f):
	"""Docorator for function expecting header 'Authorization: Bearer <token>'"""
	@wraps(f)
	async def wrapper(controller, request, *args, **kwargs):
		userid, groups, projects = await extract_and_decode_token(controller.app.kc, request)
		timestamp = datetime.now().strftime("%I:%M%p on %B %d, %Y")
		controller.app.logger.info(f'{timestamp}\t{userid}\t{",".join(groups)}\t'
			  f'{str(request.url)}-{request.method}')
		return await f(controller, request, userid=userid, groups=groups, projects=projects, *args, **kwargs)
	return wrapper


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
