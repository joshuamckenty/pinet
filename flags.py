# vim: tabstop=4 shiftwidth=4 softtabstop=4
import contrib

from gflags import *

#
# __GLOBAL FLAGS ONLY__
# Define any app-specific flags in their own files, docs at:
# http://code.google.com/p/python-gflags/source/browse/trunk/gflags.py#39

DEFINE_bool('verbose', False, 'show debug output')
