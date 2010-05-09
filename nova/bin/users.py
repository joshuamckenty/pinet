#!/usr/bin/env python

import sys
from nova.auth.users import UserManager
import nova.flags
FLAGS = nova.flags.FLAGS

def usage():
    print 'usage: %s (command)' % sys.argv[0]
    print '   -c (username) [access] [secret] - create a user'
    print '   -a (username) [access] [secret] - create an admin'
    print '   -d (username)                   - delete a user'
    print '   -k (username)                   - access & secret for user'
    print '   -e (username) [filename.zip]    - generate new X509 cert for user'

def print_export(user):
    print 'export EC2_ACCESS_KEY=%s' % user.access
    print 'export EC2_SECRET_KEY=%s' % user.secret

if __name__ == "__main__":
    FLAGS.fake_users = True
    FLAGS.ca_path="/srv/cloud/CA"
    FLAGS.keys_path="/srv/cloud/keys"
    # sys.argv = FLAGS(sys.argv)

    manager = UserManager()
    if len(sys.argv) == 2 and sys.argv[1] == '-l':
        for user in manager.get_users():
            print user.name
        sys.exit(0)
    if len(sys.argv) > 2:
        if sys.argv[1] == '-a':
            access, secret = None, None
            if len(sys.argv) > 3:
                access = sys.argv[3]
            if len(sys.argv) > 4:
                secret = sys.argv[4]
            manager.create_user(sys.argv[2], access, secret, True)
            user = manager.get_user(sys.argv[2])
            print_export(user)
        elif sys.argv[1] == '-c':
            access, secret = None, None
            if len(sys.argv) > 3:
                access = sys.argv[3]
            if len(sys.argv) > 4:
                secret = sys.argv[4]
            manager.create_user(sys.argv[2], access, secret)
            user = manager.get_user(sys.argv[2])
            print_export(user)
        elif sys.argv[1] == '-d':
            manager.delete_user(sys.argv[2])
        elif sys.argv[1] == '-k':
            user = manager.get_user(sys.argv[2])
            if user:
                print_export(user)
            else:
                print("User doesnt exist")
        elif sys.argv[1] == '-e':
            user = manager.get_user(sys.argv[2])
            if user:
                fname = 'nova.zip'
                if len(sys.argv) > 3:
                    fname = sys.argv[3]
                with open(fname, 'w') as f:
                    f.write(user.get_credentials())
        else:
            usage()
            sys.exit(2)
        sys.exit(0)
    else:
        usage()
        sys.exit(2)
