#!/usr/bin/python
import logging
import random
import os
import sys
import tornado.httpserver
import tornado.ioloop
import tornado.web
import settings
from daemon import Daemon
from api import invoke_request
import contrib # adds contrib to the path
import call

_log = logging.getLogger()

class RootRequestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('listening')
        
class APIRequestHandler(tornado.web.RequestHandler):
    def get(self, section):
        
        args = self.request.arguments
        
        try:
            access_key = args.pop('AWSAccessKeyId')
            signature_method = args.pop('SignatureMethod')
            signature_version = args.pop('SignatureVersion')
            signature = args.pop('Signature')
            version = args.pop('Version')
            timestamp = args.pop('Timestamp')
        except KeyError:
            raise tornado.web.HTTPError(400)

        try:
            action = args.pop('Action')[0]
        except Exception:
            raise tornado.web.HTTPError(400)
            
        # TODO: Access key authorization
        # if request not authorized:
        #    raise tornado.web.HTTPError(403)

        _log.info('action: %s' % action)

        for key, value in args.items():
            _log.info('arg: %s\t\tval: %s' % (key, value))

        #try:
        response = invoke_request(action, **args)
        #except ValueError, e:
        #    _log.warning()
        
        # TODO: Wrap response in AWS XML format  
        self.set_header('Content-Type', 'text/xml')
        self.write(response)

    def post(self, section):
        reservation_id = 'r-%06d' % random.randint(0,1000000)
        for num in range(int(self.request.arguments['MaxCount'][0])):
            instance_id = 'i-%06d' % random.randint(0,1000000)
            call.send_message('node', {"method": "run_instance", "args" : {"instance_id": instance_id}}, wait=False)

        self._error('unhandled', "args: %s" % str(self.request.arguments))

    def _error(self, code, message):
        self._status_code = 400
        self.set_header('Content-Type', 'text/xml')
        self.write('<?xml version="1.0"?>')
        self.write('<Response><Errors><Error><Code>%s</Code><Message>%s</Message></Error></Errors><RequestID>?</RequestID></Response>' % (code, message))
        

application = tornado.web.Application([
    (r'/', RootRequestHandler),
    (r'/services/([A-Za-z0-9]+)/', APIRequestHandler),
])

class APIServerDaemon(Daemon):
#    def start(self):
#        print 'Starting API daemon on port %s' % settings.CC_PORT
#        logging.debug('Starting API daemon on port %s' % settings.CC_PORT)
#        super(APIServerDaemon, self).start()

#    def restart(self):
#        print 'Restarting API daemon on port %s' % settings.CC_PORT
#        super(APIServerDaemon, self).restart()

#    def stop(self):
#        print 'Stopping API daemon...'
#        super(APIServerDaemon, self).stop()

    def run(self):
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(settings.CC_PORT)
        logging.debug('Started HTTP server on %s' % (settings.CC_PORT))
        tornado.ioloop.IOLoop.instance().start()

def usage():
    print 'usage: %s start|stop|restart' % sys.argv[0]

if __name__ == "__main__":
    # TODO: Log timestamp and formatting.
    logfile = os.path.join(settings.LOG_PATH, 'apiserver.log')
    logging.basicConfig(level=logging.DEBUG, filename=logfile, filemode='a')
    daemon = APIServerDaemon(os.path.join(settings.PID_PATH, 'apiserver.pid'), stdout=logfile, stderr=logfile)
    
    if len(sys.argv) == 2:
        if sys.argv[1] == 'start':
            daemon.start()
        elif sys.argv[1] == 'stop':
            daemon.stop()
        elif sys.argv[1] == 'restart':
            daemon.restart()
        else:
            usage()
            sys.exit(2)
        sys.exit(0)
    else:
        usage()
        sys.exit(2)




