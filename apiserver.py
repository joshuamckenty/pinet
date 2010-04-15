#!/usr/bin/python
import logging # TODO: Log timestamp and formatting.
import random
import os
import sys
import tornado.httpserver
import tornado.ioloop
import tornado.web

import contrib # adds contrib to the path
import call
import calllib
import utils
import exception

import cloud
from cloud_worker import CLOUD_TOPIC
from users import UserManager
from apirequest import APIRequest

_log = logging.getLogger()
_app = None

class RootRequestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('listening')
        
class APIRequestHandler(tornado.web.RequestHandler):
    def get(self, controller_name):
        self.execute(controller_name)

    def execute(self, controller_name):
        # Obtain the appropriate controller for this request.
        try:
            controller = self.application.controllers[controller_name]
        except KeyError:
            self._error('unhandled', 'no controller named %s' % controller_name)
            return
        
        args = self.request.arguments
        
        # Read request signature.
        try:
            signature = args.pop('Signature')[0]
        except:
            raise Tornado.web.HTTPError(400)
            
        # Make a copy of arguments for authentication and signature verification.
        auth_params = {} 
        for key, value in args.items():
            auth_params[key] = value[0]

        # Get requested action and remove authentication arguments for final request.
        try:
            action = args.pop('Action')[0]
            args.pop('AWSAccessKeyId')
            args.pop('SignatureMethod')
            args.pop('SignatureVersion')
            args.pop('Version')
            args.pop('Timestamp')
        except:
            raise tornado.web.HTTPError(400)

        # Authenticate the request.
        user = self.application.user_manager.authenticate (
            auth_params,
            signature,
            self.request.method,
            self.request.host,
            self.request.path
        )
        
        if not user:
            raise tornado.web.HTTPError(403)

        # Add user object to args
        args['user'] = user

        _log.info('action: %s' % action)

        for key, value in args.items():
            _log.info('arg: %s\t\tval: %s' % (key, value))

        request = APIRequest(controller, action)
        d = request.send(**args)
        d.addCallback(lambda response: _log.debug(response) and response or response)
        # d.addErrback(self.senderror)

        # TODO: Wrap response in AWS XML format  
        self.set_header('Content-Type', 'text/xml')
        d.addCallbacks(self.write, self._error_callback)

    def _error_callback(self, failure):
        try:
            failure.raiseException()
        except exception.ApiError as ex:
            self._error(type(ex).__name__ + "." + ex.code, ex.message)

    def post(self, controller_name):
        self.execute(controller_name)

    def _error(self, code, message):
        self._status_code = 400
        self.set_header('Content-Type', 'text/xml')
        self.write('<?xml version="1.0"?>\n')
        self.write('<Response><Errors><Error><Code>%s</Code><Message>%s</Message></Error></Errors><RequestID>?</RequestID></Response>' % (code, message))

class APIServerApplication(tornado.web.Application):
    def __init__(self, user_manager, controllers):
        tornado.web.Application.__init__(self, [
            (r'/', RootRequestHandler),
            (r'/services/([A-Za-z0-9]+)/', APIRequestHandler),
        ])
        self.user_manager = user_manager
        self.controllers = controllers
