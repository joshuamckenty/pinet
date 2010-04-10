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


def response(message_data, message):
    print "response", message_data
    message.ack()
    sys.exit(0)

def call(module, msg, callback = response):
    msg_id = uuid.uuid4().hex
    msg = anyjson.deserialize(msg)
    msg.update({'_msg_id': msg_id})
    print msg
    consumer = messaging.Consumer(connection=conn, queue=msg_id, exchange=msg_id)
    consumer.register_callback(callback)

    publisher = messaging.Publisher(connection=conn, queue=module, exchange=module)
    publisher.send(msg)
    publisher.close()

    consumer.wait()

import time

class synccall(object):
  def __init__(self):
    self.done = False
  def resp(self, data, msg):
    self.data = data
    self.msg = msg
    msg.ack()
    self.done = True
  def call_sync(self, module, msg):
    print "Making sync call..."
    if os.fork() == 0:
      print "Sync call in the child thread..."
      call(module, msg, self.resp)
      exit(0)
    print "Sync call in the parent thread..."
    while not self.done:
      time.sleep(1)
    return self.data
