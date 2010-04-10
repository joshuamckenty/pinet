#!/usr/bin/python
import logging
import os
import sys
import tornado.httpserver
import tornado.ioloop
import tornado.web
import settings
from daemon import Daemon

_log = logging.getLogger()

class RootRequestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('listening')
        
class APIRequestHandler(tornado.web.RequestHandler):
    def get(self):
        # TODO: Access key authorization
        
        # try:
        #    access_key = self.request.arguments.pop('AWSAccessKeyId')
        #    signature_method = self.request.arguments.pop('SignatureMethod')
        #    signature = self.request.arguments.pop('Signature')
        #    timestamp = self.request.arguments.pop('Timestamp')
        # except:
        #    raise tornado.web.HTTPError(400)
        
        # if request not authorized:
        #    raise tornado.web.HTTPError(403)
        
        try:
            action = self.request.arguments['Action']
        except:
            raise tornado.web.HTTPError(400)
            
        _log.info('action: %s' % action)

        for key, value in self.request.arguments.items():
            s = 'arg: %s\t\tval: %s' % (key, value)
            self.write(s)
            _log.info(s)

application = tornado.web.Application([
    (r'/', RootRequestHandler),
    (r'/services/Configuration/', APIRequestHandler),
])

"""
Describe Images:
GET /services/Configuration/?AWSAccessKeyId=WKy3rMzOWPouVOxK1p3Ar1C2uRBwa2FBXnCw&Action=DescribeImages&SignatureMethod=HmacSHA256&SignatureVersion=2&Timestamp=2010-04-10T05%3A03%3A20&Version=2009-04-04&Signature=HK1JomeEWCT/eANCkzQQN%2BgJTMd16pXhxlMdt3dgKtE%3D HTTP/1.1\r\nHost: 127.0.0.1:8773\r\nAccept-Encoding: identity\r\nUser-Agent: Boto/1.8d (darwin)\r\n\r\n
reply: 'HTTP/1.1 200 OK\r\n'
header: Content-Length: 2040
header: Content-Type: application/xml; charset=UTF-8
[Image:emi-CD1310B7, Image:emi-2DB60D30, Image:eri-5CB612F8, Image:eki-218811E8, Image:emi-5F64130F, Image:emi-6D76134E]


Describe Instances:
GET /services/Configuration/?AWSAccessKeyId=WKy3rMzOWPouVOxK1p3Ar1C2uRBwa2FBXnCw&Action=DescribeInstances&SignatureMethod=HmacSHA256&SignatureVersion=2&Timestamp=2010-04-10T05%3A16%3A27&Version=2009-04-04&Signature=UOwe8GTxfNuFGzGvWRMqdb2kBDDw10R3cqIJFZLiGEU%3D HTTP/1.1\r\nHost: 127.0.0.1:8773\r\nAccept-Encoding: identity\r\nUser-Agent: Boto/1.8d (darwin)\r\n\r\n

Create Security Group:
GET /services/Configuration/?AWSAccessKeyId=WKy3rMzOWPouVOxK1p3Ar1C2uRBwa2FBXnCw&Action=CreateSecurityGroup&GroupDescription=description&GroupName=name&SignatureMethod=HmacSHA256&SignatureVersion=2&Timestamp=2010-04-10T05%3A27%3A47&Version=2009-04-04&Signature=3f4O2BVgHEe0LfbND%2BPbsWfoG3js5nSQ2n/ocUtBJ0o%3D HTTP/1.1\r\nHost: 127.0.0.1:8773\r\nAccept-Encoding: identity\r\nUser-Agent: Boto/1.8d (darwin)\r\n\r\n

reply: 'HTTP/1.1 200 OK\r\n'
header: Content-Length: 188
header: Content-Type: application/xml; charset=UTF-8
SecurityGroup:name

"""

class APIServerDaemon(Daemon):
    def start(self):
        print 'Starting daemon...'
        super(APIServerDaemon, self).start()

    def restart(self):
        print 'Restarting daemon...'
        super(APIServerDaemon, self).restart()

    def stop(self):
        print 'Stopping daemon...'
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



