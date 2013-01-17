# -*- coding: utf-8 -*-
# Copyright (C) 2012 Oskar Skoog. Released under GPL.

from flask import g, request, jsonify

import kom
from komsession import KomSession, KomSessionError, to_dict

from httpkom import app, bp
from errors import error_response
from misc import empty_response, get_bool_arg_with_default
from sessions import requires_session, requires_login


@bp.route('/persons/<int:pers_no>/memberships/<int:conf_no>', methods=['PUT'])
@requires_login
def persons_put_membership(pers_no, conf_no):
    """Add the person as member to the given conference, or update an
    existing membership.
    
    Optional parameters in the body:
    
    ===========  =======  =================================================================
    Key          Type     Values
    ===========  =======  =================================================================
    priority     int      (Default 100) The priority of the membership.
    where        int      (Default 0) The position in the membership list.
    ===========  =======  =================================================================
    
    .. rubric:: Request
    
    ::
    
      PUT /<server_id>/persons/<pers_no>/memberships/<conf_no> HTTP/1.1
      
      {
        "priority": 100,
        "where": 3
      }
    
    .. rubric:: Response
    
    Success::
    
      HTTP/1.1 204 OK
    
    If the person or conference do not exist::
    
      HTTP/1.1 404 NOT FOUND
    
    .. rubric:: Example
    
    ::
    
      curl -v -X PUT -H "Content-Type: application/json" -d { "priority": 100 } \\
           "http://localhost:5001/lyskom/persons/14506/memberships/6"
    
    """
    priority = int(request.json.get('priority', 100))
    where = int(request.json.get('where', 0))
    try:
        g.ksession.add_membership(pers_no, conf_no, priority, where)
        return empty_response(204)
    except (kom.UndefinedPerson, kom.UndefinedConference) as ex:
        return error_response(404, kom_error=ex)


@bp.route('/persons/<int:pers_no>/memberships/<int:conf_no>', methods=['DELETE'])
@requires_login
def persons_delete_membership(pers_no, conf_no):
    """Remove the person's membership in the given conference.
    
    .. rubric:: Request
    
    ::
    
      DELETE /<server_id>/persons/<pers_no>/memberships/<conf_no> HTTP/1.1
    
    .. rubric:: Response
    
    Success::
    
      HTTP/1.1 204 OK
    
    If the person or conference do not exist, or if the membership do
    not exist::
    
      HTTP/1.1 404 NOT FOUND
    
    .. rubric:: Example
    
    ::
    
      curl -v -X DELETE "http://localhost:5001/lyskom/persons/14506/memberships/6"
    
    """
    try:
        g.ksession.delete_membership(pers_no, conf_no)
        return empty_response(204)
    except (kom.UndefinedPerson, kom.UndefinedConference, kom.NotMember) as ex:
        return error_response(404, kom_error=ex)


@bp.route('/persons/current/memberships/<int:conf_no>/unread', methods=['POST'])
@requires_login
def persons_set_unread(conf_no):
    """Set number of unread texts in current person's membership for
    the given conference.
    
    .. rubric:: Request
    
    ::
    
      POST /<server_id>/persons/current/memberships/<conf_no>/unread HTTP/1.1
      
      {
        "no_of_unread": 17
      }
    
    .. rubric:: Response
    
    ::
    
      HTTP/1.1 204 OK
    
    .. rubric:: Example
    
    ::
    
      curl -v -X POST -H "Content-Type: application/json" \\
           -d { "no_of_unread": 17 } \\
           http://localhost:5001/lyskom/persons/current/memberships/14506/unread
    
    """
    # The property in the JSON object body is just a wrapper because
    # most (all?) JSON libraries doesn't handle just sending a number
    # in the body; they expect/require an object or an array.
    try:
        no_of_unread = int(request.json['no_of_unread'])
    except KeyError as ex:
        return error_response(400, error_msg='Missing "no_of_unread".')
    
    g.ksession.set_unread(conf_no, no_of_unread)
    return empty_response(204)


@bp.route('/persons/<int:pers_no>/memberships/<int:conf_no>')
@requires_login
def persons_get_membership(pers_no, conf_no):
    """Get a person's membership for a conference.
    
    .. rubric:: Request
    
    ::
    
      GET /<server_id>/persons/<pers_no>/memberships/<conf_no> HTTP/1.0
    
    .. rubric:: Responses
    
    ::
    
      HTTP/1.0 200 OK
      
      {
        "pers_no": <pers_no>,
        "conference": {
          "conf_name": "Oskars Testperson", 
          "conf_no": <conf_no>
        }, 
        "priority": 255, 
        "added_at": "2012-04-28 19:49:11", 
        "position": 3, 
        "type": {
          "passive": 0, 
          "secret": 0, 
          "passive_message_invert": 0, 
          "invitation": 0
        }, 
        "last_time_read": "2012-08-19 17:14:46", 
        "added_by": {
          "pers_no": 14506, 
          "pers_name": "Oskars Testperson"
        }
      }
    
    Not a member::
    
      HTTP/1.0 404 NOT FOUND
    
    .. rubric:: Example
    
    ::
    
      curl -v -X GET "http://localhost:5001/lyskom/persons/14506/memberships/14506"
    
    """
    try:
        return jsonify(to_dict(g.ksession.get_membership(pers_no, conf_no), True, g.ksession))
    except kom.NotMember as ex:
        return error_response(404, kom_error=ex)


@bp.route('/persons/<int:pers_no>/memberships/<int:conf_no>/unread')
@requires_login
def persons_get_membership_unread(pers_no, conf_no):
    """Get membershup unread for a person's membership.
    
    .. rubric:: Request
    
    ::
    
      GET /<server_id>/persons/<pers_no>/memberships/<conf_no>/unread HTTP/1.0
    
    .. rubric:: Responses
    
    ::
    
      HTTP/1.0 200 OK
      
      {
        "pers_no": <pers_no>,
        "conf_no": <conf_no>,
        "no_of_unread": 2,
        "unread_texts": [
          19831603,
          19831620
        ]
      }
    
    Not a member::
    
      HTTP/1.0 404 NOT FOUND
    
    .. rubric:: Example
    
    ::
    
      curl -v -X GET "http://localhost:5001/lyskom/persons/14506/memberships/14506/unread"
    
    """
    try:
        return jsonify(to_dict(g.ksession.get_membership_unread(pers_no, conf_no),
                               True, g.ksession))
    except kom.NotMember as ex:
        return error_response(404, kom_error=ex)


@bp.route('/persons/<int:pers_no>/memberships/')
@requires_login
def persons_list_memberships(pers_no):
    """Get list of a person's memberships.
    
    Query parameters:
    
    ===============  =======  =================================================================
    Key              Type     Values
    ===============  =======  =================================================================
    unread           boolean  :true: Return memberships with unread texts in. The protocol A
                                     spec says: "The result is guaranteed to include all
                                     conferences where pers-no has unread texts. It may also
                                     return some extra conferences. Passive memberships are
                                     never returned." See persons_list_membership_unreads() if
                                     you want the exact list of conferences with unread.
                              :false: (Default) Return all memberships.
    passive          boolean  :true: Include passive memberships.
                              :false: (Default) Do not include passive memberships.
    ===============  =======  =================================================================
    
    .. rubric:: Request
    
    ::
    
      GET /<server_id>/persons/<pers_no>/memberships/ HTTP/1.1
    
    .. rubric:: Response
    
    ::
    
      HTTP/1.1 200 OK
      
      {
        "list": [
          {
            "pers_no": <pers_no>,
            "conference": {
              "conf_name": "Oskars Testperson", 
              "conf_no": 14506
            }, 
            "priority": 255, 
            "added_at": "2012-04-28 19:49:11", 
            "position": 3, 
            "type": {
              "passive": 0, 
              "secret": 0, 
              "passive_message_invert": 0, 
              "invitation": 0
            }, 
            "last_time_read": "2012-08-19 17:14:46", 
            "added_by": {
              "pers_no": 14506, 
              "pers_name": "Oskars Testperson"
            },
            
            "no_of_unread": null,
            "unread_texts": null
          },
          
          ...
        ]
      }
    
    .. rubric:: Example
    
    ::
    
      curl -v -X GET "http://localhost:5001/lyskom/persons/14506/memberships/?unread=true"
    
    """
    unread = get_bool_arg_with_default(request.args, 'unread', False)
    passive = get_bool_arg_with_default(request.args, 'passive', False)
    memberships = g.ksession.get_memberships(pers_no, unread, passive)
    return jsonify(list=to_dict(memberships, True, g.ksession))


@bp.route('/persons/<int:pers_no>/memberships/unread/')
@requires_login
def persons_list_membership_unreads(pers_no):
    """Get list of membership unreads for a person's memberships.
    
    .. rubric:: Request
    
    ::
    
      GET /<server_id>/persons/<pers_no>/memberships/unread/ HTTP/1.1
    
    .. rubric:: Response
    
    ::
    
      HTTP/1.1 200 OK
      
      {
        "list": [
          {
            "pers_no": <pers_no>,
            "conf_no": <conf_no>,
            "no_of_unread": 2,
            "unread_texts": [
              19831603,
              19831620
            ]
          },
          ...
        ]
      }
    
    .. rubric:: Example
    
    ::
    
      curl -v -X GET "http://localhost:5001/lyskom/persons/14506/memberships/?unread=true"
    
    """
    membership_unreads = g.ksession.get_membership_unreads(pers_no)
    return jsonify(list=to_dict(membership_unreads, True, g.ksession))