# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging

import nova.contrib
from nova.objectstore import handler
from nova import server
from nova.auth import users

from tornado import httpserver
from tornado import ioloop

from nova import flags
FLAGS = flags.FLAGS
import nova.objectstore # for flags

# flags.DEFINE_integer('s3_port', 3333, 's3 port')
# flags.DEFINE_integer('s3_internal_port', 3334, 's3 port')
# flags.DEFINE_string('s3_host', '172.24.226.1', 's3 host')

def main(argv):
    # FIXME: if this log statement isn't here, no logging
    # appears from other files and app won't start daemonized
    logging.debug('Started HTTP server on %s' % (FLAGS.s3_internal_port))
    app = handler.Application(users.UserManager())
    server = httpserver.HTTPServer(app)
    server.listen(FLAGS.s3_internal_port)
    ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    server.serve('oss', main)
