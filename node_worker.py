# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import subprocess

import node

import contrib
from carrot import connection
from carrot import messaging 
import calllib
import utils

NODE_TOPIC='node'


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
        

    # TODO(termie): make these into singletons?
    n = node.Node(options)
    conn = utils.get_rabbit_conn()
    consumer = calllib.PinetLibraryConsumer(connection=conn, module=NODE_TOPIC, lib=n)
    logging.debug('About to wait for consumer with callback')
    consumer.wait()
