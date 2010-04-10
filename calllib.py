# vim: tabstop=4 shiftwidth=4
import os
import sys
import uuid
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.split(__file__)[0], 'contrib')))

import anyjson

from carrot import connection
from carrot import messaging

conn = connection.BrokerConnection(hostname="localhost", port=5672,
                                   userid="guest", password="guest",
                                   virtual_host="/")


def call_sync(module, msg):
    print "Making sync call..."
    msg_id = uuid.uuid4().hex
    msg = anyjson.deserialize(msg)
    msg.update({'_msg_id': msg_id})
    # print msg
    consumer = messaging.Consumer(connection=conn, queue=msg_id, exchange=msg_id, auto_delete=True, routing_key=msg_id, exchange_type="direct")

    publisher = messaging.Publisher(connection=conn, queue=module, exchange="pinet", exchange_type="topic", routing_key=module)
    publisher.send(msg)
    publisher.close()
    data = None
    while data is None:
        for msg in consumer.iterqueue(limit=1):
            data = msg.decode()
        time.sleep(1)
    return data['result']
