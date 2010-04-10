#!/usr/bin/python
import sys
import tornado.httpserver
import tornado.ioloop
import tornado.web
import settings
from daemon import Daemon

class APIRequestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

application = tornado.web.Application([
    (r"/", APIRequestHandler),
])

class APIDaemon(Daemon):
    def start(self):
        print 'Starting daemon...'
        super(APIDaemon, self).start()

    def restart(self):
        print 'Restarting daemon...'
        super(APIDaemon, self).restart()

    def stop(self):
        print 'Stopping daemon...'
        super(APIDaemon, self).stop()

    def run(self):
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(settings.CC_PORT)
        tornado.ioloop.IOLoop.instance().start()

def usage():
    print 'usage: %s start|stop|restart' % sys.argv[0]

if __name__ == "__main__":
    daemon = APIDaemon('/tmp/apiserver.pid')
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



