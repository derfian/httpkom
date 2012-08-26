# -*- coding: utf-8 -*-
# Copyright (C) 2012 Oskar Skoog. Released under GPL.

import json
import functools

from flask import g, abort, request, jsonify, make_response, Response

import kom
from komsession import KomSession, KomSessionError, AmbiguousName, NameNotFound, to_dict

from httpkom import app
from errors import error_response
from misc import empty_response
import version


_default_client_name = 'httpkom'
_kom_server = app.config['HTTPKOM_LYSKOM_SERVER']

kom_sessions = {}


def requires_session(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        g.ksession = _get_komsession(_get_session_id())
        if g.ksession:
            return f(*args, **kwargs)
        
        return empty_response(401)
    return decorated


def optional_session(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        g.ksession = _get_komsession(_get_session_id())
        return f(*args, **kwargs)
    return decorated


def _create_komsession(pers_no, password, client_name, client_version):
    ksession = KomSession(_kom_server)
    ksession.connect()
    try:
        ksession.login(pers_no, password, client_name, client_version)
        # todo: check for exceptions that we should return 401 for. or
        # should that be done here? we don't want to return http stuff here
    except:
        ksession.disconnect()
        raise
    return ksession

def _save_komsession(session_id, ksession):
    kom_sessions[session_id] = ksession

def _delete_komsession():
    if 'session_id' in request.cookies:
        session_id = request.cookies.get('session_id')
        if session_id in kom_sessions:
            del kom_sessions[session_id]

def _get_session_id():
    if 'session_id' in request.cookies:
        return request.cookies.get('session_id')
    return None

def _get_komsession(session_id):
    if session_id is not None:
        if session_id in kom_sessions:
            return kom_sessions[session_id]
    
    return None

def _login(pers_no,
           password,
           client_name=_default_client_name,
           client_version=version.__version__):
    #app.logger.debug("Logging in")
    ksession = _create_komsession(pers_no, password, client_name, client_version)
    _save_komsession(ksession.id, ksession)
    return ksession

def _logout(ksession):
    #app.logger.debug("Logging out")
    try:
        ksession.logout()
        ksession.disconnect()
    finally:
        _delete_komsession()


@app.route("/sessions/", methods=['POST'])
def sessions_create():
    """Create a new session (i.e. login).
    
    Note: If the login is successful, the matched full name will be
    returned in the response.
    
    If no client is specified in the request, "httpkom" will be used.
    
    .. rubric:: Request
    
    ::
    
      POST /sessions/ HTTP/1.1
      
      {
        "person": { "pers_no": 14506 },
        "passwd": "test123",
        "client": { "name": "jskom", "version": "0.2" }
      }
    
    .. rubric:: Responses
    
    Successful login::
    
      HTTP/1.0 200 OK
      Set-Cookie: session_id=033556ee-3e52-423f-9c9a-d85aed7688a1; expires=Sat, 19-May-2012 12:44:51 GMT; Max-Age=604800; Path=/
      
      { "id": "033556ee-3e52-423f-9c9a-d85aed7688a1",
        "person": { "pers_no": 14506, "pers_name": "Oskars testperson" },
        "client": { "name": "jskom", "version": "0.2" } }
    
    Failed login::
    
      HTTP/1.1 401 Unauthorized
      
    .. rubric:: Example
    
    ::
    
      curl -b cookies.txt -c cookies.txt -v \\
           -X POST -H "Content-Type: application/json" \\
           -d '{ "person": { "pers_no": 14506 }, "passwd": "test123" }' \\
            http://localhost:5001/sessions/
    
    """
    old_ksession = _get_komsession(_get_session_id())
    if old_ksession:
        # already loggedin, logout first, then try to login with the
        # supplied credentials.
        _logout(old_ksession)
    
    try:
        person = request.json['person']
        if person is None:
            return error_response(400, error_msg='"person" is null.')
    except KeyError as ex:
        return error_response(400, error_msg='Missing "person".')
    
    try:
        pers_no = person['pers_no']
        if pers_no is None:
            return error_response(400, error_msg='"pers_no" in "person" is null.')
    except KeyError as ex:
        return error_response(400, error_msg='Missing "pers_no" in "person".')

    try:
        passwd = request.json['passwd']
        if passwd is None:
            return error_response(400, error_msg='"passwd" is null.')
    except KeyError as ex:
        return error_response(400, error_msg='Missing "passwd".')
    
    try:
        if 'client' in request.json and request.json['client'] is not None:
            ksession = _login(pers_no, passwd,
                              request.json['client']['name'], request.json['client']['version'])
        else:
            ksession = _login(pers_no, passwd)
        
        response = jsonify(to_dict(ksession, True, ksession))
        response.set_cookie('session_id', domain=app.config['HTTPKOM_COOKIE_DOMAIN'],
                            value=ksession.id, max_age=7*24*60*60)
        return response
    except (kom.InvalidPassword, kom.UndefinedPerson, kom.LoginDisallowed,
            kom.ConferenceZero) as ex:
        return error_response(401, kom_error=ex)


@app.route("/sessions/<string:session_id>")
def sessions_get(session_id):
    """Get information about a session. Usable for checking if your
    session is still valid.
    
    .. rubric:: Request
    
    ::
    
      GET /sessions/033556ee-3e52-423f-9c9a-d85aed7688a1 HTTP/1.1
    
    .. rubric:: Responses
    
    Session exists (i.e. logged in)::
    
      HTTP/1.1 200 OK
      
      { "id": "033556ee-3e52-423f-9c9a-d85aed7688a1",
        "person": { "pers_no": 14506, "pers_name": "Oskars testperson" },
        "client": { "name": "jskom", "version": "0.2" } }
    
    Session does not exist (i.e. not logged in)::
    
      HTTP/1.1 404 Not Found
    
    .. rubric:: Example
    
    ::
    
      curl -b cookies.txt -c cookies.txt -v \\
           -X GET http://localhost:5001/sessions/abc123
    
    """
    session_id = _get_session_id()
    ksession = _get_komsession(session_id)
    if ksession:
        return jsonify(to_dict(ksession, True, ksession))
    else:
        return empty_response(404)


@app.route("/sessions/<string:session_id>", methods=['DELETE'])
def sessions_delete(session_id):
    """Delete a session (i.e. logout).
    
    .. rubric:: Request
    
    ::
    
      DELETE /sessions/033556ee-3e52-423f-9c9a-d85aed7688a1 HTTP/1.1
    
    .. rubric:: Responses
    
    Session exist::
    
      HTTP/1.1 204 No Content
    
    Session does not exist::
    
      HTTP/1.1 404 Not Found
      Set-Cookie: session_id=; expires=Thu, 01-Jan-1970 00:00:00 GMT; Path=/
    
    .. rubric:: Example
    
    ::
    
      curl -b cookies.txt -c cookies.txt -v \\
           -X DELETE http://localhost:5001/sessions/abc123
    
    """
    ksession = _get_komsession(session_id)
    if ksession:
        _logout(ksession)
        response = empty_response(204)
        response.set_cookie('session_id', value='', expires=0)
        return response
    else:
        return empty_response(404)


@app.route("/sessions/current/working-conference", methods=['POST'])
@requires_session
def sessions_change_working_conference():
    """Change current working conference of the current session.
    
    .. rubric:: Request
    
    ::
    
      POST /sessions/current/working-conference HTTP/1.1
      
      {
        "conf_no": 14506,
      }
    
    .. rubric:: Responses
    
    ::
    
      HTTP/1.1 204 No Content
    
    .. rubric:: Example
    
    ::
    
      curl -b cookies.txt -c cookies.txt -v \\
           -X POST -H "Content-Type: application/json" \\
           -d '{ "conf_no": 14506 }' \\
           http://localhost:5001/sessions/current/working-conference
    
    """
    try:
        conf_no = request.json['conf_no']
        if conf_no is None:
            return error_response(400, error_msg='"conf_no" is null.')
    except KeyError as ex:
        return error_response(400, error_msg='Missing "conf_no".')
    
    try:
        g.ksession.change_conference(conf_no)
        return empty_response(204)
    except kom.Error as ex:
        return error_response(400, kom_error=ex)
