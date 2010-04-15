# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging

import contrib
from tornado import httpserver
from tornado import ioloop

import apiserver
import calllib
import flags
import server

import admin
import cloud
import users


FLAGS = flags.FLAGS


flags.DEFINE_integer('cc_port', 8773, 'cloud controller port')


def main(argv):
    user_manager = users.UserManager()
    controllers = { 
        'Cloud': cloud.CloudController(),
        'Admin': admin.AdminController(user_manager)
    }
    _app = apiserver.APIServerApplication(user_manager, controllers)

    conn = calllib.Connection.instance()

    # TODO: Attach another consumer for admin controller.
    consumer = calllib.AdapterConsumer(connection=conn,
                                       topic=FLAGS.cloud_topic,
                                       proxy=controllers['Cloud'])

    io_inst = ioloop.IOLoop.instance()
    
    # TODO: Do we need to keep track of 'injected' ?
    injected = consumer.attachToTornado(io_inst)

    http_server = httpserver.HTTPServer(_app)
    http_server.listen(FLAGS.cc_port)
    logging.debug('Started HTTP server on %s' % (FLAGS.cc_port))
    ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    server.serve('api_worker', main)
