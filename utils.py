# vim: soft
"""
Popen bits.

"""
import logging
import subprocess
import calllib
import random

def execute(cmd, input=None):
    obj = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if input != None:
        result = obj.communicate(input)
    else:
        result = obj.communicate()
    obj.stdin.close()
    return result

def runthis(prompt, cmd):
    logging.debug("Running %s" % (cmd))
    logging.debug(prompt % (subprocess.call(cmd.split(" "))))

def generate_mac():
    mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff), random.randint(0x00, 0xff)
           ]
    return ':'.join(map(lambda x: "%02x" % x, mac))
