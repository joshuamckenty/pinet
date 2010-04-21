# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import StringIO
import time
import unittest
from xml.etree import ElementTree

import contrib
import mox
from tornado import ioloop
from twisted.internet import defer

import calllib
import cloud
import exception
import flags
import node
import test


FLAGS = flags.FLAGS


class CloudTestCase(test.BaseTestCase):
    def setUp(self):
        super(CloudTestCase, self).setUp()

        self.conn = calllib.Connection.instance()
        logging.getLogger().setLevel(logging.DEBUG)

        # set up our cloud
        self.cloud = cloud.CloudController()
        self.cloud_consumer = calllib.AdapterConsumer(connection=self.conn,
                                                      topic=FLAGS.cloud_topic,
                                                      proxy=self.cloud)
        self.injected.append(self.cloud_consumer.attach_to_tornado(self.ioloop))
        
        # set up a node
        self.node = node.Node()
        self.node_consumer = calllib.AdapterConsumer(connection=self.conn,
                                                     topic=FLAGS.node_topic,
                                                     proxy=self.node)
        self.injected.append(self.node_consumer.attach_to_tornado(self.ioloop))

    def test_console_output(self):
        if FLAGS.fake_libvirt:
            logging.debug("Can't test instances without a real virtual env.")
            return
        instance_id = 'foo'
        inst = yield self.node.run_instance(instance_id)
        output = yield self.cloud.get_console_output(None, [instance_id])
        logging.debug(output)
        self.assert_(output)
        rv = yield self.node.terminate_instance(instance_id)

    def test_run_instances(self):
        if FLAGS.fake_libvirt:
            logging.debug("Can't test instances without a real virtual env.")
            return
        image_id = FLAGS.default_image
        instance_type = FLAGS.default_instance_type
        max_count = 1
        kwargs = {'image_id': image_id,
                  'instance_type': instance_type,
                  'max_count': max_count}
        rv = yield self.cloud.run_instances(None, **kwargs)
        # TODO: check for proper response
        instance = rv['reservationSet'][0][rv['reservationSet'][0].keys()[0]][0]
        logging.debug("Need to watch instance %s until it's running..." % instance['instance_id'])
        while True:
            rv = yield defer.succeed(time.sleep(1))
            info = self.cloud._get_instance(instance['instance_id'])
            logging.debug(info['state'])
            if info['state'] == node.Instance.RUNNING:
                break
        self.assert_(rv)
        # if not FLAGS.fake_libvirt:
        #     time.sleep(45) # Should use boto for polling here
        # for reservations in rv['reservationSet']:
            #for res_id in reservations.keys():
              # logging.debug(reservations[res_id])
             # for instance in reservations[res_id]:  
          #  for instance in reservations[reservations.keys()[0]]:  
           #     logging.debug("Terminating instance %s" % instance['instance_id'])
            #    rv = yield self.node.terminate_instance(instance['instance_id'])

