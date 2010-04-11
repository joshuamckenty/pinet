#!/usr/bin/python
import logging
import os
import sys
import tornado.httpserver
import tornado.ioloop
import tornado.web
import settings
from daemon import Daemon
from api import invoke_request
from users import UserManager

_log = logging.getLogger()

class RootRequestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('listening')
        
class APIRequestHandler(tornado.web.RequestHandler):
    def get(self, section):
        
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
        manager = UserManager()
        _log.info('host: %s' % self.request.host)
        if not manager.authenticate(params,
                                    signature,
                                    'GET',
                                    self.request.host,
                                    self.request.path):
            raise tornado.web.HTTPError(403)

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
            

application = tornado.web.Application([
    (r'/', RootRequestHandler),
    (r'/services/([A-Za-z0-9]+)/', APIRequestHandler),
])

class APIServerDaemon(Daemon):
    def start(self):
        print 'Starting API daemon on port %s' % settings.CC_PORT
        super(APIServerDaemon, self).start()

    def restart(self):
        print 'Restarting API daemon on port %s' % settings.CC_PORT
        super(APIServerDaemon, self).restart()

    def stop(self):
        print 'Stopping API daemon...'
        super(APIServerDaemon, self).stop()

    def run(self):
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(settings.CC_PORT)
        tornado.ioloop.IOLoop.instance().start()

def usage():
    print 'usage: %s start|stop|restart' % sys.argv[0]

if __name__ == "__main__":
    # TODO: Log timestamp and formatting.
    logging.basicConfig(level=logging.DEBUG, filename=os.path.join(settings.LOG_PATH, 'apiserver.log'), filemode='a')
    daemon = APIServerDaemon(os.path.join(settings.PID_PATH, 'apiserver.pid'))
    
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




