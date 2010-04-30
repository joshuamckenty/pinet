#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import logging.handlers
import sys

import contrib
from carrot import connection
from carrot import messaging
from tornado import ioloop

import calllib
import flags
import network
import server


FLAGS = flags.FLAGS
flags.DEFINE_integer('node_report_state_interval', 10, 
                     'seconds between nodes reporting state to cloud',
                     lower_bound=1)


def main(argv):
    logging.warn('HEYA')
    n = network.NetworkNode()
    d = n.adopt_instances()
    d.addCallback(lambda x: logging.info('Adopted %d instances', x))

    conn = calllib.Connection.instance()
    consumer_all = calllib.AdapterConsumer(
            connection=conn,
            topic='%s' % FLAGS.node_topic,
            proxy=n)
    
    consumer_node = calllib.AdapterConsumer(
            connection=conn,
            topic='%s.%s' % (FLAGS.node_topic, FLAGS.node_name),
            proxy=n)

    io_inst = ioloop.IOLoop.instance()
    scheduler = ioloop.PeriodicCallback(
            lambda: n.report_state(),
            FLAGS.node_report_state_interval * 1000,
            io_loop=io_inst)

    injected = consumer_all.attachToTornado(io_inst)
    injected = consumer_node.attachToTornado(io_inst)
    scheduler.start()
    io_inst.start()


if __name__ == '__main__':
    server.serve('node_worker', main)
