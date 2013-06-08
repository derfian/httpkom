# -*- coding: utf-8 -*-
# Copyright (C) 2012 Oskar Skoog. Released under GPL.

import os
import logging
from logging.handlers import TimedRotatingFileHandler

from flask import Flask, Blueprint, request, jsonify, g, abort


class default_settings:
    DEBUG = False
    LOG_FILE = None
    LOG_LEVEL = logging.WARNING
    
    HTTPKOM_LYSKOM_SERVERS = [
        ('lyslyskom', 'LysKOM', 'kom.lysator.liu.se', 4894)
        ]
    
    HTTPKOM_CONNECTION_HEADER = 'Httpkom-Connection'

    HTTPKOM_CROSSDOMAIN_ALLOWED_ORIGINS = '*'
    HTTPKOM_CROSSDOMAIN_MAX_AGE = 0
    HTTPKOM_CROSSDOMAIN_ALLOW_HEADERS = [ 'Origin', 'Accept', 'Content-Type', 'X-Requested-With',
                                          'Cache-Control' ]
    HTTPKOM_CROSSDOMAIN_EXPOSE_HEADERS = [ 'Cache-Control' ]
    HTTPKOM_CROSSDOMAIN_ALLOW_METHODS = [ 'GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD' ]


app = Flask(__name__)
app.config.from_object(default_settings)
if 'HTTPKOM_SETTINGS' in os.environ:
    app.config.from_envvar('HTTPKOM_SETTINGS')
else:
    app.logger.info("No environment variable HTTPKOM_SETTINGS found, using default settings.")

app.config['HTTPKOM_CROSSDOMAIN_ALLOW_HEADERS'].append(app.config['HTTPKOM_CONNECTION_HEADER'])
app.config['HTTPKOM_CROSSDOMAIN_EXPOSE_HEADERS'].append(app.config['HTTPKOM_CONNECTION_HEADER'])


class Server(object):
    def __init__(self, sid, name, host, port=4894):
        self.id = sid
        self.name = name
        self.host = host
        self.port = port
    
    def to_dict(self):
        return { 'id': self.id, 'name': self.name, 'host': self.host, 'port': self.port }

_servers = dict()
for server in app.config['HTTPKOM_LYSKOM_SERVERS']:
    _servers[server[0]] = Server(server[0], server[1], server[2], server[3])


bp = Blueprint('frontend', __name__, url_prefix='/<string:server_id>')

# http://flask.pocoo.org/docs/patterns/urlprocessors/
@bp.url_value_preprocessor
def pull_server_id(endpoint, values):
    server_id = values.pop('server_id')
    if server_id in _servers:
        g.server = _servers[server_id]
    else:
        # No such server
        abort(404)


if not app.debug and app.config['LOG_FILE'] is not None:
    # keep 7 days of logs, rotated every midnight
    file_handler = TimedRotatingFileHandler(
        app.config['LOG_FILE'], when='midnight', interval=1, backupCount=7)
    
    file_handler.setFormatter(logging.Formatter(
           '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
            ))
    
    file_handler.setLevel(app.config['LOG_LEVEL'])
    
    app.logger.addHandler(file_handler)
    app.logger.setLevel(app.config['LOG_LEVEL'])
    app.logger.info("Finished setting up file logger.");



# Load app parts
import conferences
import sessions
import texts
import persons
import memberships
import errors


app.register_blueprint(bp)


@app.after_request
def allow_crossdomain(resp):
    def is_allowed(origin):
        allowed_origins = app.config['HTTPKOM_CROSSDOMAIN_ALLOWED_ORIGINS']
        if allowed_origins is not None:
            if isinstance(allowed_origins, basestring) and allowed_origins == '*':
                return True
            
            if origin in allowed_origins:
                return True
        
        return False
            
    
    if 'Origin' in request.headers:
        h = resp.headers
        origin = request.headers['Origin']
        if is_allowed(origin):
            h['Access-Control-Allow-Origin'] = origin
                          
            h['Access-Control-Allow-Methods'] = \
                ', '.join(app.config['HTTPKOM_CROSSDOMAIN_ALLOW_METHODS'])
            
            h['Access-Control-Max-Age'] = \
                str(app.config['HTTPKOM_CROSSDOMAIN_MAX_AGE'])
            
            h['Access-Control-Allow-Headers'] = \
                ', '.join(app.config['HTTPKOM_CROSSDOMAIN_ALLOW_HEADERS'])
            
            h['Access-Control-Expose-Headers'] = \
                ', '.join(app.config['HTTPKOM_CROSSDOMAIN_EXPOSE_HEADERS'])
        else:
            h['Access-Control-Allow-Origin'] = 'null'
    
    return resp

@app.after_request
def ios6_cache_fix(resp):
    # Safari in iOS 6 has excessive caching, so this is to stop it
    # from caching our POST requests. We also add Cache-Control:
    # no-cache to any request that doesn't already have a
    # Cache-Control header.
    if request.method == 'POST' or 'Cache-Control' not in resp.headers:
        resp.headers['Cache-Control'] = 'no-cache'
    return resp

@app.route("/")
def index():
    servers = dict([ (s.id, s.to_dict()) for s in _servers.values() ])
    return jsonify(servers)
