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

import utils
conn = utils.get_rabbit_conn()

class PinetControlConsumer(messaging.Consumer):
    exchange_type = "topic" 
    def __init__(self, connection=None, module="broadcast"):
        self.queue = module
        self.routing_key = module
        self.exchange = settings.CONTROL_EXCHANGE
        super(PinetControlConsumer, self).__init__(connection=connection)

class PinetLibraryConsumer(PinetControlConsumer):
    def __init__(self, connection=None, module="broadcast", lib=None):
        logging.debug('Initing the Library Consumer for %s' % (module))
        self.lib = lib
        super(PinetLibraryConsumer, self).__init__(connection=connection, module=module)
 
    def receive(self, message_data, message):
        logging.debug('received %s' % (message_data))

        try:
            msg_id = message_data.pop('_msg_id')
        except Exception:
            logging.exception("no msg_id found")
            message.ack()
            return

        method = message_data.get('method')
        args = message_data.get('args', {})

        node_func = getattr(self.lib, method)
        node_args = dict((str(k), v) for k, v in args.iteritems())
        
        rval = node_func(**node_args)
        msg_reply(msg_id, rval)
        message.ack()


class PinetControlPublisher(messaging.Publisher):
    exchange_type = "topic" 
    def __init__(self, connection=None, module="broadcast"):
        self.routing_key = module
        self.exchange = settings.CONTROL_EXCHANGE
        super(PinetControlPublisher, self).__init__(connection=connection)
        
class PinetDirectConsumer(messaging.Consumer):
    exchange_type = "direct" 
    def __init__(self, connection=None, msg_id=None):
        self.queue = msg_id
        self.routing_key = msg_id
        self.exchange = msg_id
        self.auto_delete = True
        super(PinetDirectConsumer, self).__init__(connection=connection)

class PinetDirectPublisher(messaging.Publisher):
    exchange_type = "direct"
    def __init__(self, connection=None, msg_id=None):
        self.routing_key = msg_id
        self.exchange = msg_id
        self.auto_delete = True
        super(PinetDirectPublisher, self).__init__(connection=connection)

def msg_reply(msg_id, rval):
    publisher = PinetDirectPublisher(connection=conn, msg_id=msg_id)
    publisher.send({'result': rval})
    publisher.close()

def call_sync(module, msg):
    logging.debug("Making synchronous (blocking) call...")
    msg_id = uuid.uuid4().hex
    msg = anyjson.deserialize(msg)
    msg.update({'_msg_id': msg_id})
    logging.debug("MSG_ID is %s" % (msg_id))

    consumer = PinetDirectConsumer(connection=conn, msg_id=msg_id)
    publisher = PinetControlPublisher(connection=conn, module=module)
    publisher.send(msg)
    publisher.close()
    data = None
    while data is None:
        for msg in consumer.iterqueue(limit=1):
            data = msg.decode()
        time.sleep(1)
    return data['result']
