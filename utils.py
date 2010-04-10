"""
Popen bits.

"""
import subprocess

def runthis(prompt, cmd):
    print "Running %s" % (cmd)
    print prompt % (subprocess.call(cmd.split(" ")))
