# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
Popen bits.

"""
import logging
import os.path
import subprocess
import calllib
import random

def abspath(s):
  return os.path.join(os.path.dirname(__file__), s)

def runthis(prompt, cmd):
    logging.debug("Running %s" % (cmd))
    logging.debug(prompt % (subprocess.call(cmd.split(" "))))

def generate_mac():
    mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff), random.randint(0x00, 0xff)
           ]
    return ':'.join(map(lambda x: "%02x" % x, mac))
