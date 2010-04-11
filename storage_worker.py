# vim: tabstop=4 shiftwidth=4 softtabstop
"""
Storage Worker proxies AMQP calls into the storage library.
"""
import logging

import calllib
import node
import storage
import utils


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
        
    bs = storage.BlockStore(options)
    conn = utils.get_rabbit_conn()
    consumer = calllib.AdapterConsumer(connection=conn, topic=NODE_TOPIC, proxy=bs)
    consumer.wait()
