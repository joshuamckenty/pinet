#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4
import os
import sys
import node
import storage
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.split(__file__)[0], 'contrib')))

from carrot import connection
from carrot import messaging 

logging.getLogger().setLevel(logging.DEBUG)

bs = storage.BlockStore()

conn = connection.BrokerConnection(hostname="localhost", port=5672,
                                   userid="guest", password="guest",
                                   virtual_host="/")

def router(message_data, message):
    logging.debug('response %s', message_data)

    try:
        msg_id = message_data.pop('_msg_id')
    except Exception:
        logging.exception("ouch")
        message.ack()
        return

    logging.debug('foobar')

    message.ack()
    rval = getattr(bs, message_data.get('method'))(**dict([(str(k), v) for k, v in message_data.get('args', {}).iteritems()]))
    logging.debug("Trying to send: %s" % rval)

    publisher = messaging.Publisher(connection=conn, queue=msg_id, exchange=msg_id, auto_delete = True, exchange_type="direct", routing_key=msg_id)
    publisher.send({'result': rval})
    publisher.close()

consumer = messaging.Consumer(connection=conn, queue="storage", exchange="pinet", exchange_type="topic", routing_key="storage")
consumer.register_callback(router)
consumer.wait()

