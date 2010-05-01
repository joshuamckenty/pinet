# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging

import contrib
from tornado import httpserver
from tornado import ioloop
import s3server
import flags
import server
import users

FLAGS = flags.FLAGS

def main(argv):
    app = s3server.S3Application(users.UserManager())
    server = httpserver.HTTPServer(app)
    server.listen(FLAGS.s3_internal_port)
    # FIXME: if this log statement isn't here, no logging
    # appears from other files
    logging.debug('Started HTTP server on %s' % (FLAGS.s3_internal_port))
    ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    server.serve('s3_worker', main)
