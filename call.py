# vim: tabstop=4 shiftwidth=4
import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.split(__file__)[0], 'contrib')))

import anyjson

from carrot import connection
from carrot import messaging

conn = connection.BrokerConnection(hostname="localhost", port=5672,
                                   userid="guest", password="guest",
                                   virtual_host="/")

msg_id = uuid.uuid4().hex
msg = anyjson.deserialize(sys.argv[2])
msg.update({'_msg_id': msg_id})
print msg


def response(message_data, message):
    print "response", message_data
    message.ack()
    sys.exit(0)

consumer = messaging.Consumer(connection=conn, queue=msg_id, exchange=msg_id)
consumer.register_callback(response)

publisher = messaging.Publisher(connection=conn, queue=sys.argv[1], exchange=sys.argv[1])
publisher.send(msg)
publisher.close()

consumer.wait()

