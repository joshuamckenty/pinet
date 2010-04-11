# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import uuid
import sys

import contrib # adds contrib to the path
import anyjson

from carrot import connection
from carrot import messaging


logging.getLogger().setLevel(logging.DEBUG)

import utils
conn = utils.get_rabbit_conn()

def generic_response(message_data, message):
    logging.debug('response %s', message_data)
    message.ack()
    sys.exit(0)

def send_message(topic, message):
    msg_id = uuid.uuid4().hex
    message.update({'_msg_id': msg_id})
    logging.debug('topic is %s', topic)
    logging.debug('message %s', message)

    consumer = messaging.Consumer(connection=conn,
                                  queue=msg_id,
                                  exchange=msg_id,
                                  auto_delete=True,
                                  exchange_type="direct",
                                  routing_key=msg_id)
    consumer.register_callback(generic_response)

    publisher = messaging.Publisher(connection=conn,
                                    exchange="pinet",
                                    exchange_type="topic",
                                    routing_key=topic)
    publisher.send(message)
    publisher.close()

    consumer.wait()
    
    
if __name__ == "__main__":
    send_message(sys.argv[1], anyjson.deserialize(sys.argv[2]))
