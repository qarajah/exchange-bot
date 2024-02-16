import json
import os
import redis
from functools import wraps
from flask import make_response, request

LOCAL = False

try:
    import config as config
    SECRET_KEY = config.SECRET_KEY
    API_KEY = config.API_KEY
    API_SECRET = config.API_SECRET
    USER = config.USER
    PASSWORD = config.PASSWORD
    CODE = config.CODE
    TG_TOKEN = config.TG_TOKEN
    TG_CHAT = config.TG_CHAT
    LOCAL = True
    DEBUG = True
    REDIS_URL = config.REDIS_URL
    print('CONFIG SUCCESS')
except:
    print('ACCESS OS ENVIRON CREDENTIALS')
    SECRET_KEY = os.environ['SECRET_KEY']
    USER = os.environ['USER']
    PASSWORD = os.environ['PASSWORD']
    API_KEY = os.environ['API_KEY']
    API_SECRET = os.environ['API_SECRET']
    CODE = os.environ['CODE']
    TG_TOKEN = os.environ['TG_TOKEN']
    TG_CHAT = os.environ['TG_CHAT']
    REDIS_URL = os.environ['REDIS_URL']
    DEBUG = False

if REDIS_URL:
    if LOCAL:
        r = redis.from_url(REDIS_URL, ssl_cert_reqs=None, decode_responses=True)
    else:
        ## For Render URL
        r = redis.from_url(REDIS_URL, decode_responses=True)


if not r.get('ASSETS'):
    r.set('ASSETS', json.dumps({}))

ASSETS = json.loads(r.get('ASSETS'))

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        username = USER
        passcode = PASSWORD

        if auth and auth.username == username and auth.password == passcode:
            return f(*args, **kwargs)
        return make_response("<h1>Access denied!</h1>", 401, {'WWW-Authenticate': 'Basic realm="Login required!"'})

    return decorated

