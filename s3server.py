#!/usr/bin/python
import logging
import os
import sys
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.s3server
import settings
from daemon import Daemon

class S3ServerDaemon(Daemon):
    def start(self):
        print 'Starting S3 daemon on port %s...' % settings.S3_PORT
        super(S3ServerDaemon, self).start()

    def restart(self):
        print 'Retarting S3 daemon on port %s...' % settings.S3_PORT
        super(S3ServerDaemon, self).restart()

    def stop(self):
        print 'Stopping S3 daemon...'
        super(S3ServerDaemon, self).stop()

    def run(self):
        app = tornado.s3server.S3Application(settings.S3_PATH, 0)
        server = tornado.httpserver.HTTPServer(app)
        server.listen(settings.S3_PORT) 
        tornado.ioloop.IOLoop.instance().start()

def usage():
    print 'usage: %s start|stop|restart' % sys.argv[0]

if __name__ == "__main__":
    # TODO: Log timestamp and formatting.
    logging.basicConfig(level=logging.DEBUG, filename=os.path.join(settings.LOG_PATH, 's3server.log'), filemode='a')
    daemon = S3ServerDaemon(os.path.join(settings.PID_PATH, 's3server.pid'))
    
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