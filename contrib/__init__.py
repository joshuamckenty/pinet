import os
import sys

CONTRIB_PATH = os.path.abspath(os.path.dirname(__file__))

paths = [CONTRIB_PATH,
         os.path.join(CONTRIB_PATH, 'pymox'),
         os.path.join(CONTRIB_PATH, 'tornado')
         ]

for p in paths:
  if p not in sys.path:
    sys.path.insert(0, p)
