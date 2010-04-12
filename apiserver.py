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
from api import handle_request
from users import UserManager
import contrib # adds contrib to the path
import call
import calllib
import utils

import cloud
from cloud import CLOUD_TOPIC

_log = logging.getLogger()
_app = None

class RootRequestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('listening')
        
class APIRequestHandler(tornado.web.RequestHandler):
    def get(self, controller_name):
        self.execute(controller_name)

    def execute(self, controller_name):
        try:
            controller = self.application.controllers[controller_name]
        except KeyError:
            self._error('unhandled', 'no controller named %s' % controller_name)
            return
        
        args = self.request.arguments
        params = {} # copy of args to pass to authentication
        for key, value in args.items():
            params[key] = value[0]
        del params['Signature']

        try:
            access_key = args.pop('AWSAccessKeyId')[0]
            signature_method = args.pop('SignatureMethod')[0]
            signature_version = args.pop('SignatureVersion')[0]
            signature = args.pop('Signature')[0]
            version = args.pop('Version')[0]
            timestamp = args.pop('Timestamp')[0]
        except KeyError:
            raise tornado.web.HTTPError(400)

        try:
            action = args.pop('Action')[0]
        except Exception:
            raise tornado.web.HTTPError(400)
            
        # TODO: Access key authorization
        _log.info('access_key: %s' % params['AWSAccessKeyId'])
        _log.info('host: %s' % self.request.host)
        if not self.application.user_manager.authenticate(params,
                                    signature,
                                    self.request.method,
                                    self.request.host,
                                    self.request.path):
            raise tornado.web.HTTPError(403)

        _log.info('action: %s' % action)

        for key, value in args.items():
            _log.info('arg: %s\t\tval: %s' % (key, value))

        #try:
        response = handle_request(controller, action, **args)
        print response
        _log.debug(response)
        #except ValueError, e:
        #    _log.warning()
        
        # TODO: Wrap response in AWS XML format  
        self.set_header('Content-Type', 'text/xml')
        self.write(response)

    def post(self, controller_name):
        self.execute(controller_name)
        """
        reservation_id = 'r-%06d' % random.randint(0,1000000)
        for num in range(int(self.request.arguments['MaxCount'][0])):
            instance_id = 'i-%06d' % random.randint(0,1000000)
            call.send_message('node', {"method": "run_instance", "args" : {"instance_id": instance_id}}, wait=False)
        """
        self._error('unhandled', "args: %s" % str(self.request.arguments))

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
        #conn = utils.get_rabbit_conn()
        #consumer = calllib.AdapterConsumer(connection=conn, topic=CLOUD_TOPIC, proxy=controllers['Cloud'])
        #io_inst = tornado.ioloop.IOLoop.instance()
        #injected = consumer.attachToTornado(io_inst)
        daemon.start()
    elif args[0] == 'stop':
        daemon.stop()
    elif args[0] == 'restart':
        daemon.restart()
    else:
        parser.error("unknown command")
