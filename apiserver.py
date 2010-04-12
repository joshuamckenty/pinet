#!/usr/bin/python
import logging # TODO: Log timestamp and formatting.
import random
import os
import sys
import tornado.httpserver
import tornado.ioloop
import tornado.web
import settings
from daemon import Daemon

import contrib # adds contrib to the path
import call
import calllib
import utils

import cloud
from cloud import CLOUD_TOPIC
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
        authenticated = self.application.user_manager.authenticate (
            auth_params,
            signature,
            self.request.method,
            self.request.host,
            self.request.path
        )
        
        if not authenticated:
            raise tornado.web.HTTPError(403)
            
        _log.info('action: %s' % action)

        for key, value in args.items():
            _log.info('arg: %s\t\tval: %s' % (key, value))

        request = APIRequest(controller, action)
        response = request.send(**args)
        
        _log.debug(response)

        # TODO: Wrap response in AWS XML format  
        self.set_header('Content-Type', 'text/xml')
        self.write(response)

    def post(self, controller_name):
        self.execute(controller_name)

    def _error(self, code, message):
        self._status_code = 400
        self.set_header('Content-Type', 'text/xml')
        self.write('<?xml version="1.0"?>')
        self.write('<Response><Errors><Error><Code>%s</Code><Message>%s</Message></Error></Errors><RequestID>?</RequestID></Response>' % (code, message))

class APIServerApplication(tornado.web.Application):
    def __init__(self, user_manager, controllers):
        tornado.web.Application.__init__(self, [
            (r'/', RootRequestHandler),
            (r'/services/([A-Za-z0-9]+)/', APIRequestHandler),
        ])
        self.user_manager = user_manager
        self.controllers = controllers

class APIServerDaemon(Daemon):
    def run(self):
        http_server = tornado.httpserver.HTTPServer(_app)
        http_server.listen(settings.CC_PORT)
        logging.debug('Started HTTP server on %s' % (settings.CC_PORT))
        tornado.ioloop.IOLoop.instance().start()
        
        
if __name__ == "__main__":
    import optparse

    parser = optparse.OptionParser(usage='usage: %prog [options] start|stop|restart')
    parser.add_option("--use_fake", dest="use_fake",
                      help="don't actually use ldap",
                      default=False,
                      action="store_true")
    parser.add_option('-v', dest='verbose',
                      help='verbose logging',
                      default=False,
                      action='store_true')
                      
    (options, args) = parser.parse_args()
    
    if len(args) != 1:
        parser.error("missing command")
    
    if options.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
                      
    logfile = os.path.join(settings.LOG_PATH, 'apiserver.log')
    logging.basicConfig(level=logging.DEBUG, filename=logfile, filemode='a')
    daemon = APIServerDaemon(os.path.join(settings.PID_PATH, 'apiserver.pid'), stdout=logfile, stderr=logfile)
        
    if args[0] == 'start':
        if options and options.use_fake:
            user_manager = UserManager({'use_fake': True})
        else:
            user_manager = UserManager()
        controllers = { 'Cloud': cloud.CloudController(options) }
        _app = APIServerApplication(user_manager, controllers)
        conn = utils.get_rabbit_conn()
        consumer = calllib.AdapterConsumer(connection=conn, topic=CLOUD_TOPIC, proxy=controllers['Cloud'])
        io_inst = tornado.ioloop.IOLoop.instance()
        injected = consumer.attachToTornado(io_inst)
        daemon.start()
    elif args[0] == 'stop':
        daemon.stop()
    elif args[0] == 'restart':
        daemon.restart()
    else:
        parser.error("unknown command")
