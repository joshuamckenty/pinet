.. nova documentation master file, created by
   sphinx-quickstart on Sat May  1 15:17:47 2010.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to nova's documentation!
================================



an amazon/eucalyptus/rackspace cloud clone in python, amqp, tornado, ...

DEPENDENCIES
------------

* RabbitMQ: messaging queue, used for all communication between components
* OpenLDAP: users, groups (maybe cut)
* Tornado: scalable non blocking web server for api requests
* Twisted: just for the twisted.internet.defer package
* boto: python api for aws api
* M2Crypto: python library interface for openssl
* IPy: library for managing ip addresses

Recommended
-----------------
* euca2ools: python implementation of aws ec2-tools and ami tools
* build tornado to use C module for evented section

COMPONENTS
----------

<pre>
             [ User Manager ] ---- ( LDAP )
                      |  
                      |                / [ Storage ] - ( ATAoE )
[ API server ] -> [ Cloud ]  < AMQP >   
                      |                \ [ Nodes ]   - ( libvirt/kvm )
                   < HTTP >
                      |
                  [   S3  ]
</pre>

* API: receives http requests from boto, converts commands to/from API format, and sending requests to cloud controller
* Cloud Controller: global state of system, talks to ldap, s3, and node/storage workers through a queue
* Nodes: worker that spawns instances
* S3: tornado based http/s3 server
* User Manager: create/manage users, which are stored in ldap
* Network Controller: allocate and deallocate IPs and VLANs



Contents:

.. toctree::
   :maxdepth: 2
   
   modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

