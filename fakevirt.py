# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import StringIO
from xml.etree import ElementTree


class FakeVirtConnection(object):
    def __init__(self, options=None):
        self.options = options
        self.next_index = 0
        self.instances = {}

    def lookupByID(self, i):
        return self.instances[str(i)]

    def listDomainsID(self):
        return self.instances.keys()

    def lookupByName(self, instance_id):
        for x in self.instances.values():
            if x.name() == instance_id:
                return x
        raise Exception('no instance found for instance_id: %s' % instance_id)

    def createXML(self, xml, flags):
        # parse the xml :(
        xml_stringio = StringIO.StringIO(xml)

        my_xml = ElementTree.parse(xml_stringio)
        name = my_xml.find('name').text

        fake_instance = FakeVirtInstance(conn=self, 
                                         index=str(self.next_index),
                                         name=name,
                                         xml=my_xml)
        self.instances[str(self.next_index)] = fake_instance
        self.next_index += 1

    def _removeInstance(self, i):
        self.instances.pop(str(i))


class FakeVirtInstance(object):
    NOSTATE = 0x00
    RUNNING = 0x01
    BLOCKED = 0x02
    PAUSED = 0x03
    SHUTDOWN = 0x04
    SHUTOFF = 0x05
    CRASHED = 0x06

    def __init__(self, conn, index, name, xml):
        self._conn = conn
        self._destroyed = False
        self._name = name
        self._index = index
        self._state = self.RUNNING

    def name(self):
        return self._name

    def destroy(self):
        if self._state == self.SHUTOFF:
            raise Exception('instance already destroyed: %s' % self.name())
        self._state = self.SHUTOFF
        self._conn._removeInstance(self._index)

    def info(self):
        
        return [self._state, 0, 0, 0, 0]
