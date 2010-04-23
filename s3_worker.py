# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging

import contrib
from tornado import httpserver
from tornado import ioloop
import s3server
import flags
import server
import utils

FLAGS = flags.FLAGS

flags.DEFINE_string('buckets_path', utils.abspath('../buckets'), 'path to s3 buckets')
flags.DEFINE_string('images_path', utils.abspath('../images'), 'path to decrypted images')
flags.DEFINE_integer('s3_port', 3333, 's3 port')


def main(argv):
    app = s3server.S3Application(FLAGS.buckets_path, FLAGS.images_path, 0)
    server = httpserver.HTTPServer(app)
    server.listen(FLAGS.s3_port) 
    ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    server.serve('s3_worker', main)
