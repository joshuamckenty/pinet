# vim: tabstop=4 shiftwidth=4
import os
import sys
import node
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.split(__file__)[0], 'contrib')))

from carrot import connection
from carrot import messaging 

n = node.Node()

conn = connection.BrokerConnection(hostname="localhost", port=5672,
                                   userid="guest", password="guest",
                                   virtual_host="/")

def router(message_data, message):
    print "Got message: %s" % message_data

    try:
        msg_id = message_data.pop('_msg_id')
    except Exception:
        logging.exception("ouch")
        message.ack()
        return

    print "foobar"
    rval = getattr(n, message_data.get('method'))(**dict([(str(k), v) for k, v in message_data.get('args', {}).iteritems()]))
    print "Trying to send: %s" % rval

    publisher = messaging.Publisher(connection=conn, queue=msg_id, exchange=msg_id)
    publisher.send({'result': rval})
    publisher.close()
    message.ack()

consumer = messaging.Consumer(connection=conn, queue="node", exchange="node")
consumer.register_callback(router)
consumer.wait()

