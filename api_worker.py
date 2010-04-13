# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging

import contrib
from tornado import httpserver
from tornado import ioloop

import apiserver
import calllib
import cloud

import flags
import server
import users


FLAGS = flags.FLAGS


flags.DEFINE_integer('cc_port', 8773, 'cloud controller port')


def main(argv):
    if FLAGS.fake_users:
        user_manager = users.UserManager({'use_fake': True})
    else:
        user_manager = users.UserManager()

    controllers = { 'Cloud': cloud.CloudController() }
    _app = apiserver.APIServerApplication(user_manager, controllers)

    conn = calllib.Connection.instance()

    consumer = calllib.AdapterConsumer(connection=conn,
                                       topic=FLAGS.cloud_topic,
                                       proxy=controllers['Cloud'])

    io_inst = ioloop.IOLoop.instance()
    injected = consumer.attachToTornado(io_inst)

    http_server = httpserver.HTTPServer(_app)
    http_server.listen(FLAGS.cc_port)
    logging.debug('Started HTTP server on %s' % (FLAGS.cc_port))
    ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    server.serve('api_worker', main)
