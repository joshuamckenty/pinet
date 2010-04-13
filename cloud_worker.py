#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import subprocess

import node
import cloud

import contrib
from carrot import connection
from carrot import messaging 
import calllib
from tornado import ioloop

CLOUD_TOPIC='cloud'


if __name__ == '__main__':
    import optparse

    parser = optparse.OptionParser()
    parser.add_option("--use_fake", dest="use_fake",
                      help="don't actually start any instances",
                      default=False,
                      action="store_true")
    parser.add_option('-v', dest='verbose',
                      help='verbose logging',
                      default=False,
                      action='store_true')

    (options, args) = parser.parse_args()
    if options.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    cloud_controller = cloud.CloudController(options)
    conn = calllib.Connection.instance()
    consumer = calllib.AdapterConsumer(connection=conn, topic=CLOUD_TOPIC, proxy=cloud_controller)
    io_inst = ioloop.IOLoop.instance()
    injected = consumer.attachToTornado(io_inst)
    io_inst.start()
