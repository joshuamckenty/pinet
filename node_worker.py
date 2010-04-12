#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import sys

import contrib
from carrot import connection
from carrot import messaging 
from tornado import ioloop

import calllib
import flags
import node
import utils

FLAGS = flags.FLAGS

flags.DEFINE_integer('node_report_state_interval', 10, 
                     'seconds between nodes reporting state to cloud',
                     lower_bound=1)


if __name__ == '__main__':
    argv = FLAGS(sys.argv)
    
    logging.getLogger('amqplib').setLevel(logging.WARN)
    if FLAGS.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    n = node.Node()
    d = n.adopt_instances()
    d.addCallback(lambda x: logging.info('Adopted %d instances', x))

    conn = utils.get_rabbit_conn()
    consumer = calllib.AdapterConsumer(
            connection=conn, topic=FLAGS.node_topic, proxy=n)

    io_inst = ioloop.IOLoop.instance()
    scheduler = ioloop.PeriodicCallback(
            lambda: n.report_state(),
            FLAGS.node_report_state_interval * 1000,
            io_loop=io_inst)

    injected = consumer.attachToTornado(io_inst)
    scheduler.start()
    io_inst.start()
