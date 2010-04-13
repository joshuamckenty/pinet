# vim: tabstop=4 shiftwidth=4 softtabstop=4
import contrib
from tornado import httpserver
from tornado import ioloop
from tornado import s3server

import flags
import server

FLAGS = flags.FLAGS

flags.DEFINE_string('s3_path', '/var/pinet/s3', 's3 path')
flags.DEFINE_integer('s3_port', 3333, 's3 port')


def main(argv):
    app = s3server.S3Application(FLAGS.s3_path, 0)
    server = httpserver.HTTPServer(app)
    server.listen(FLAGS.s3_port) 
    ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    server.serve('s3_worker', main)
