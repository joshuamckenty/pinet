#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4
import os
import sys
import node
import storage
import logging
import utils
import calllib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.split(__file__)[0], 'contrib')))

from carrot import connection
from carrot import messaging 

NODE_TOPIC='storage'


if __name__ == '__main__':
    import optparse

    parser = optparse.OptionParser()
    parser.add_option("--use_fake", dest="use_fake",
                      help="don't actually create volumes",
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
    bs = storage.BlockStore(options)
    conn = utils.get_rabbit_conn()

    consumer = calllib.PinetLibraryConsumer(connection=conn, module=NODE_TOPIC, lib=bs)
    logging.debug('About to wait for consumer with callback')
    consumer.wait()
