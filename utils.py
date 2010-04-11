"""
Popen bits.

"""
import settings
import subprocess

import contrib
import carrot

def runthis(prompt, cmd):
    print "Running %s" % (cmd)
    print prompt % (subprocess.call(cmd.split(" ")))

def get_rabbit_conn():
    return carrot.connection.BrokerConnection(hostname=settings.RABBIT_HOST,
                                   port=settings.RABBIT_PORT,
                                   userid=settings.RABBIT_USER,
                                   password=settings.RABBIT_PASS,
                                   virtual_host=settings.RABBIT_VHOST)
