# vim: soft
"""
Popen bits.

"""
import logging
import subprocess
import calllib

def runthis(prompt, cmd):
    logging.debug("Running %s" % (cmd))
    logging.debug(prompt % (subprocess.call(cmd.split(" "))))