# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import subprocess

import node

import contrib
from carrot import connection
from carrot import messaging 


NODE_TOPIC='node'


class NodeRouter(object):
    def __init__(self, consumer):
        self.consumer = consumer

    def __call__(self, message_data, message):
        logging.debug('received %s', message_data)

        try:
            msg_id = message_data.pop('_msg_id')
        except Exception:
            logging.exception("no msg_id found")
            message.ack()
            return

        method = message_data.get('method')
        args = message_data.get('args', {})

        node_func = getattr(n, method)
        node_args = dict((str(k), v) for k, v in args.iteritems())
        
        rval = node_func(**node_args)

        publisher = messaging.Publisher(connection=conn,
                                        queue=msg_id,
                                        exchange=msg_id)
        logging.debug('send %s', rval)
        publisher.send({'result': rval})
        publisher.close()
        message.ack()


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
    conn = connection.BrokerConnection(hostname="localhost", port=5672,
                                       userid="guest", password="guest",
                                       virtual_host="/")
    consumer = messaging.Consumer(connection=conn,
                                  queue=NODE_TOPIC,
                                  exchange=NODE_TOPIC)

    router = NodeRouter(consumer)

    consumer.register_callback(router)
    consumer.wait()
