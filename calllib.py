# vim: tabstop=4 shiftwidth=4 softtabstop=4
import os
import sys
import uuid
import time
import logging
import settings

import contrib
import anyjson

from carrot import connection
from carrot import messaging

import utils
conn = utils.get_rabbit_conn()

class TopicConsumer(messaging.Consumer):
    exchange_type = "topic" 
    def __init__(self, connection=None, topic="broadcast"):
        self.queue = topic
        self.routing_key = topic
        self.exchange = settings.CONTROL_EXCHANGE
        super(TopicConsumer, self).__init__(connection=connection)

class AdapterConsumer(TopicConsumer):
    def __init__(self, connection=None, topic="broadcast", proxy=None):
        logging.debug('Initing the Adapter Consumer for %s' % (topic))
        self.proxy = proxy
        super(AdapterConsumer, self).__init__(connection=connection, topic=topic)
 
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

        node_func = getattr(self.proxy, method)
        node_args = dict((str(k), v) for k, v in args.iteritems())
        
        rval = node_func(**node_args)
        msg_reply(msg_id, rval)
        message.ack()


class TopicPublisher(messaging.Publisher):
    exchange_type = "topic" 
    def __init__(self, connection=None, topic="broadcast"):
        self.routing_key = topic
        self.exchange = settings.CONTROL_EXCHANGE
        super(TopicPublisher, self).__init__(connection=connection)
        
class DirectConsumer(messaging.Consumer):
    exchange_type = "direct" 
    def __init__(self, connection=None, msg_id=None):
        self.queue = msg_id
        self.routing_key = msg_id
        self.exchange = msg_id
        self.auto_delete = True
        super(DirectConsumer, self).__init__(connection=connection)

class DirectPublisher(messaging.Publisher):
    exchange_type = "direct"
    def __init__(self, connection=None, msg_id=None):
        self.routing_key = msg_id
        self.exchange = msg_id
        self.auto_delete = True
        super(DirectPublisher, self).__init__(connection=connection)

def msg_reply(msg_id, reply):
    publisher = DirectPublisher(connection=conn, msg_id=msg_id)
    publisher.send({'result': reply})
    publisher.close()

def call_sync(topic, msg):
    logging.debug("Making synchronous (blocking) call...")
    msg_id = uuid.uuid4().hex
    msg = anyjson.deserialize(msg)
    msg.update({'_msg_id': msg_id})
    logging.debug("MSG_ID is %s" % (msg_id))

    consumer = DirectConsumer(connection=conn, msg_id=msg_id)
    publisher = TopicPublisher(connection=conn, topic=topic)
    publisher.send(msg)
    publisher.close()
    reply = None
    while reply is None:
        reply = consumer.fetch()
        time.sleep(1)
    data = reply.decode()
    return data['result']
