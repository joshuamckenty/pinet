PiNet
=====

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
                  ( LDAP )
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

MILESTONES
==========

Alive
-----

  [x] can spawn instances via python api from a single image
  [ ] can ssh into instance spawned instances (network system mode)

Growing
-------

  [ ] Cloud init generates certs for cloud
  [ ] images stored on s3 as full files (not encrypted)
  [ ] euca-get-console-output works
  [ ] euca-terminate-instances works
  [X] euca-run-instances works
  [X] euca-describe-instances works
  [X] can launch from many different images
  [ ] can launch different sizes
  [ ] node downloads images

Works
-----

  [X] can create volumes
  [X] can destroy volumes
  [X] can attach volumes

Secure
------

  [ ] x509 certificate generation
  [ ] can list, upload and register images using real apis
  [X] users exist and have ec2 credentials
  [X] api calls are validated and ran as a user
  [ ] keypairs work
  [X] Deliver creds to user (pinetrc, etc)

Wow
----

  [ ] works with dashboard
  [ ] network with subnets/vlans works
  [ ] can allocate and attach public IPs
  [ ] security groups works
  [ ] instances can access their user-data, meta-data

Installation
============

    apt-get install python-libvirt libvirt-bin kvm rabbitmq-server python-dev python-pycurl python-simplejson m2crypto boto
    apt-get install iscsitarget aoetools vblade-persist
    # optional packages
    apt-get install euca2ools 

    # fix ec2 metadata/userdata uri - where $IP is the IP of the cloud
    iptables -t nat -A PREROUTING -s 0.0.0.0/0 -d 169.254.169.254/32 -p tcp -m tcp --dport 80 -j DNAT --to-destination $IP:8773

    # setup ldap 
    # run rabbitmq-server
    # start api_worker, s3_worker, node_worker, storage_worker
