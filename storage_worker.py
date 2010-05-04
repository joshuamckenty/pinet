#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop
"""
Storage Worker proxies AMQP calls into the storage library.
"""

import logging
import calllib
import node
import storage
import server

from tornado import ioloop

NODE_TOPIC='storage'

import flags
FLAGS = flags.FLAGS

flags.DEFINE_integer('storage_report_state_interval', 10, 
                     'seconds between broadcasting state to cloud',
                     lower_bound=1)

def main(argv):
    bs = storage.BlockStore()
    
    conn = calllib.Connection.instance()
    consumer_all = calllib.AdapterConsumer(
            connection=conn,
            topic='%s' % FLAGS.storage_topic,
            proxy=bs)
    
    consumer_node = calllib.AdapterConsumer(
            connection=conn,
            topic='%s.%s' % (FLAGS.storage_topic, FLAGS.node_name),
            proxy=bs)

    io_inst = ioloop.IOLoop.instance()
    scheduler = ioloop.PeriodicCallback(
            lambda: bs.report_state(), 
            FLAGS.storage_report_state_interval * 1000,
            io_loop=io_inst)

    injected = consumer_all.attachToTornado(io_inst)
    injected = consumer_node.attachToTornado(io_inst)
    scheduler.start()
    io_inst.start()
    
    
if __name__ == '__main__':
    server.serve('storage_worker', main)

