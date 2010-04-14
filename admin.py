"""
NEEDS:

A module that we can import and use to perform admin functions such as:

1. Get a list of node workers along with current instance data

(assuming cloud stores node data similar to this:)

{ 'node_hostname': 'node001',
  'instances': [
        { 'instance_id': 'i-ABCDEFG', 'state': 'running' },
        { 'instance_id': 'i-HIJKLMN', 'state': 'terminated' },
    ]
},

etc.


2. Create / delete user


3. Download credentials/X509 as zip file
"""