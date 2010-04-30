# vim: tabstop=4 shiftwidth=4 softtabstop=4
import os
import sys
import uuid
import time
import logging

import contrib
import anyjson

from carrot import connection
from carrot import messaging
from tornado import ioloop
from twisted.internet import defer

import fakerabbit
import flags

FLAGS = flags.FLAGS

flags.DEFINE_boolean('fake_rabbit', False, 'use a fake rabbit')
flags.DEFINE_string('rabbit_host', 'localhost', 'rabbit host')
flags.DEFINE_integer('rabbit_port', 5672, 'rabbit port')
flags.DEFINE_string('rabbit_userid', 'guest', 'rabbit userid')
flags.DEFINE_string('rabbit_password', 'guest', 'rabbit password')
flags.DEFINE_string('rabbit_virtual_host', '/', 'rabbit virtual host')
flags.DEFINE_string('control_exchange', 'nova', 'the main exchange to connect to')

_log = logging.getLogger('amqplib')
_log.setLevel(logging.WARN)

class Connection(connection.BrokerConnection):
    @classmethod
    def instance(cls):
        if not hasattr(cls, '_instance'):
            params = dict(hostname=FLAGS.rabbit_host,
                          port=FLAGS.rabbit_port,
                          userid=FLAGS.rabbit_userid,
                          password=FLAGS.rabbit_password,
                          virtual_host=FLAGS.rabbit_virtual_host)

            if FLAGS.fake_rabbit:
                params['backend_cls'] = fakerabbit.Backend

            cls._instance = cls(**params)
        return cls._instance


class Consumer(messaging.Consumer):
    # TODO(termie): it would be nice to give these some way of automatically
    #               cleaning up after themselves
    def attach_to_tornado(self, io_inst=None):
        if io_inst is None:
            io_inst = ioloop.IOLoop.instance()

        injected = ioloop.PeriodicCallback(
            lambda: self.fetch(enable_callbacks=True), 1, io_loop=io_inst)
        injected.start()
        return injected

    attachToTornado = attach_to_tornado


class Publisher(messaging.Publisher):
    pass


class TopicConsumer(Consumer):
    exchange_type = "topic" 
    def __init__(self, connection=None, topic="broadcast"):
        self.queue = topic
        self.routing_key = topic
        self.exchange = FLAGS.control_exchange
        super(TopicConsumer, self).__init__(connection=connection)


class AdapterConsumer(TopicConsumer):
    def __init__(self, connection=None, topic="broadcast", proxy=None):
        _log.debug('Initing the Adapter Consumer for %s' % (topic))
        self.proxy = proxy
        super(AdapterConsumer, self).__init__(connection=connection, topic=topic)
 
    def receive(self, message_data, message):
        _log.debug('received %s' % (message_data))
        msg_id = message_data.pop('_msg_id', None)

        method = message_data.get('method')
        args = message_data.get('args', {})
        if not method:
            return

        node_func = getattr(self.proxy, str(method))     
        node_args = dict((str(k), v) for k, v in args.iteritems())
        d = defer.maybeDeferred(node_func, **node_args)
        if msg_id:
            d.addCallback(lambda rval: msg_reply(msg_id, rval))
            d.addErrback(lambda e: msg_reply(msg_id, str(e)))
        message.ack()
        return


class TopicPublisher(Publisher):
    exchange_type = "topic" 
    def __init__(self, connection=None, topic="broadcast"):
        self.routing_key = topic
        self.exchange = FLAGS.control_exchange
        super(TopicPublisher, self).__init__(connection=connection)
        

class DirectConsumer(Consumer):
    exchange_type = "direct" 
    def __init__(self, connection=None, msg_id=None):
        self.queue = msg_id
        self.routing_key = msg_id
        self.exchange = msg_id
        self.auto_delete = True
        super(DirectConsumer, self).__init__(connection=connection)


class DirectPublisher(Publisher):
    exchange_type = "direct"
    def __init__(self, connection=None, msg_id=None):
        self.routing_key = msg_id
        self.exchange = msg_id
        self.auto_delete = True
        super(DirectPublisher, self).__init__(connection=connection)


def msg_reply(msg_id, reply):
    conn = Connection.instance()
    publisher = DirectPublisher(connection=conn, msg_id=msg_id)
    
    try:
        publisher.send({'result': reply})
    except TypeError:
        publisher.send(
                {'result': dict((k, repr(v)) 
                                for k, v in reply.__dict__.iteritems())
                 })
    publisher.close()


def call(topic, msg):
    _log.debug("Making asynchronous call...")
    msg_id = uuid.uuid4().hex
    msg.update({'_msg_id': msg_id})
    _log.debug("MSG_ID is %s" % (msg_id))
    
    conn = Connection.instance()
    d = defer.Deferred()
    consumer = DirectConsumer(connection=conn, msg_id=msg_id)
    consumer.register_callback(lambda data, message: d.callback(data))
    injected = consumer.attach_to_tornado()

    # clean up after the injected listened and return x
    d.addCallback(lambda x: injected.stop() and x or x)

    publisher = TopicPublisher(connection=conn, topic=topic)
    publisher.send(msg)
    publisher.close()
    return d


def cast(topic, msg):
    _log.debug("Making asynchronous cast...")
    conn = Connection.instance()
    publisher = TopicPublisher(connection=conn, topic=topic)
    publisher.send(msg)
    publisher.close()
