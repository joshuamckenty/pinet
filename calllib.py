# vim: tabstop=4 shiftwidth=4
import os
import sys
import uuid
import time
import logging
import settings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.split(__file__)[0], 'contrib')))

import anyjson

from carrot import connection
from carrot import messaging

conn = connection.BrokerConnection(hostname=settings.RABBIT_HOST,
                                   port=settings.RABBIT_PORT,
                                   userid=settings.RABBIT_USER,
                                   password=settings.RABBIT_PASS,
                                   virtual_host=settings.RABBIT_VHOST)

class PinetControlConsumer(messaging.Consumer):
    exchange_type = "topic" 
    def __init__(self, connection=None, module="broadcast"):
        self.queue = module
        self.routing_key = module
        self.exchange = settings.CONTROL_EXCHANGE
        super(PinetControlConsumer, self).__init__(connection=connection)
        
class PinetDirectConsumer(messaging.Consumer):
    exchange_type = "direct" 
    def __init__(self, connection=None, msg_id=None):
        self.queue = msg_id
        self.routing_key = msg_id
        self.exchange = msg_id
        self.auto_delete = True
        super(PinetDirectConsumer, self).__init__(connection=connection)

def call_sync(module, msg):
    logging.debug("Making synchronous (blocking) call...")
    msg_id = uuid.uuid4().hex
    msg = anyjson.deserialize(msg)
    msg.update({'_msg_id': msg_id})
    logging.debug("MSG_ID is %s" % (msg_id))

    consumer = PinetDirectConsumer(connection=conn, msg_id=msg_id)

    publisher = messaging.Publisher(connection=conn, queue=module, exchange="pinet", exchange_type="topic", routing_key=module)
    publisher.send(msg)
    publisher.close()
    data = None
    while data is None:
        for msg in consumer.iterqueue(limit=1):
            data = msg.decode()
        time.sleep(1)
    return data['result']
