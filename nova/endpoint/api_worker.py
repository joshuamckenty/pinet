# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging

from nova import contrib
from tornado import httpserver
from tornado import ioloop

from nova import rpc
from nova import flags
from nova import server

import admin
import cloud
from nova.auth import users

import nova.objectstore # for flags
import api

FLAGS = flags.FLAGS

flags.DEFINE_integer('cloudpipe_interval', 30,
                     'seconds between check for cloudpipe spawns (0 to disable)')


def main(argv):
    user_manager = users.UserManager()
    controllers = {
        'Cloud': cloud.CloudController(),
        'Admin': admin.AdminController(user_manager)
    }
    _app = api.APIServerApplication(user_manager, controllers)

    conn = rpc.Connection.instance()
    consumer = rpc.AdapterConsumer(connection=conn,
                                       topic=FLAGS.cloud_topic,
                                       proxy=controllers['Cloud'])

    io_inst = ioloop.IOLoop.instance()
    if FLAGS.cloudpipe_interval > 0:
        cloudcron_scheduler = ioloop.PeriodicCallback(
            lambda: controllers['Cloud'].cloudcron(),
            FLAGS.cloudpipe_interval * 1000,
            io_loop=io_inst)

    # TODO: Do we need to keep track of 'injected' ?
    injected = consumer.attach_to_tornado(io_inst)

    http_server = httpserver.HTTPServer(_app)
    http_server.listen(FLAGS.cc_port)
    logging.debug('Started HTTP server on %s' % (FLAGS.cc_port))
    if FLAGS.cloudpipe_interval > 0:
        cloudcron_scheduler.start()
    io_inst.start()


if __name__ == '__main__':
    server.serve('api_worker', main)
