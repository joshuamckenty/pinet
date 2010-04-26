# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
Popen bits.

"""
import logging
import os.path
import subprocess
import calllib
import random

def fetchfile(url, target):
    logging.debug("Fetching %s" % url)
#    c = pycurl.Curl()
#    fp = open(target, "wb")
#    c.setopt(c.URL, url)
#    c.setopt(c.WRITEDATA, fp)
#    c.perform()
#    c.close()
#    fp.close()
    execute("curl %s -o %s" % (url, target))

def execute(cmd, input=None):
    #logging.debug("Running %s" % (cmd))
    obj = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = None
    if input != None:
        result = obj.communicate(input)
    else:
        result = obj.communicate()
    obj.stdin.close()
    if obj.returncode:
        logging.debug("Result was %s" % (obj.returncode))
    return result

def abspath(s):
  return os.path.join(os.path.dirname(__file__), s)


def debug(arg):
    logging.debug('debug in callback: %s', arg)
    return arg

def runthis(prompt, cmd):
    logging.debug("Running %s" % (cmd))
    logging.debug(prompt % (subprocess.call(cmd.split(" "))))


def generate_mac():
    mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff), random.randint(0x00, 0xff)
           ]
    return ':'.join(map(lambda x: "%02x" % x, mac))
