# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import logging.handlers
import os
import signal
import sys
import time

import contrib
import daemon
from daemon import pidlockfile

import flags

FLAGS = flags.FLAGS

flags.DEFINE_bool('daemonize', False, 'daemonize this process')

# NOTE(termie): right now I am defaulting to using syslog when we daemonize
#               it may be better to do something else -shrug-

# (Devin) I think we should let each process have its own log file
#         and put it in /var/logs/pinet/(appname).log
#         This makes debugging much easier and cuts down on sys log clutter.
flags.DEFINE_bool('use_syslog', True, 'output to syslog when daemonizing')
flags.DEFINE_string('logfile', None, 'log file to output to')
flags.DEFINE_string('pidfile', None, 'pid file to output to')
flags.DEFINE_string('working_directory', './', 'working directory...')


def stop(pidfile):
    """
    Stop the daemon
    """
    # Get the pid from the pidfile
    try:
        pf = file(pidfile,'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        pid = None

    if not pid:
        message = "pidfile %s does not exist. Daemon not running?\n"
        sys.stderr.write(message % pidfile)
        return # not an error in a restart

    # Try killing the daemon process    
    try:
        while 1:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.1)
    except OSError, err:
        err = str(err)
        if err.find("No such process") > 0:
            if os.path.exists(pidfile):
                os.remove(pidfile)
        else:
            print str(err)
            sys.exit(1)


def serve(name, main):
    argv = FLAGS(sys.argv)

    if not FLAGS.pidfile:
        FLAGS.pidfile = '%s.pid' % name

    action = 'start'
    if len(argv) > 1:
        action = argv.pop()

    if action == 'stop':
        stop(FLAGS.pidfile)
        sys.exit()
    elif action == 'restart':
        stop(FLAGS.pidfile)
    elif action == 'start':
        pass
    else:
        print 'usage: %s [options] [start|stop|restart]' % argv[0]
        sys.exit(1)

    logging.getLogger('amqplib').setLevel(logging.WARN)
    if FLAGS.daemonize:
        logger = logging.getLogger()
        formatter = logging.Formatter(
                name + '(%(name)s): %(levelname)s %(message)s')
        if FLAGS.use_syslog and not FLAGS.logfile:
            syslog = logging.handlers.SysLogHandler(address='/dev/log')
            syslog.setFormatter(formatter)
            logger.addHandler(syslog)
        else:
            if not FLAGS.logfile:
                FLAGS.logfile = '%s.log' % name
            logfile = logging.handlers.FileHandler(FLAGS.logfile)
            logfile.setFormatter(formatter)
            logger.addHandler(logfile)
        stdin, stdout, stderr = None, None, None
    else:
        stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr

    if FLAGS.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    with daemon.DaemonContext(
            detach_process=FLAGS.daemonize,
            working_directory=FLAGS.working_directory,
            pidfile=pidlockfile.TimeoutPIDLockFile(FLAGS.pidfile,
                                                   acquire_timeout=1,
                                                   threaded=False),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr
            ):
        main(argv)
