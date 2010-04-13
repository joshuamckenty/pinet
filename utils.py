# vim: soft
"""
Popen bits.

"""
import logging
import subprocess
import calllib

def runthis(prompt, cmd):
    print "Running %s" % (cmd)
    print prompt % (subprocess.call(cmd.split(" ")))

def get_rabbit_conn():
    logging.warning('DEPRECATED: get_rabbit_conn is deprecated, use calllib.Connection.instance() instead')
    return calllib.Connection.instance()
