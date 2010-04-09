PiNet
=====

a eucalyptus clone in python, amqp, tornado, ...

DEPENDENCIES
============

RabbitMQ: messaging queue, used for all communication between components
OpenLDAP: users, groups (maybe cut)
Tornado:  scalable non blocking web server for api requests

COMPONENTS
==========

API: receives http requests from boto, and sends commands to other components via amqp
Controller: global state of system and 
Nodes: worker that spawns instances
S3: tornado based http/s3 server

MILESTONES
==========

Alive
-----

  [ ] can spawn instances via python api from a single image
  [ ] can ssh into instance spawned instances (network system mode)

Growing
-------

  [ ] images stored on s3 as full files (not encrypted)
  [ ] euca-get-console-output works
  [ ] euca-terminate-instances works
  [ ] euca-run-instances works
  [ ] euca-describe-instances works
  [ ] can launch from many different images
  [ ] can launch different sizes

Works
-----

  [ ] can create volumes
  [ ] can destroy volumes
  [ ] can attach volumes

Secure
------

  [ ] can list, upload and register images
  [ ] euca-describe-images works
  [ ] users exist and have ec2 credentials
  [ ] api calls are validated and ran as a user
  [ ] x509 certificate generation
  [ ] security groups works

Wow
----

  [ ] works with dashboard
  [ ] network with subnets/vlans works
  [ ] can allocate and attach public IPs   
  [ ] instances can access their user-data, meta-data

Installation
============

  sudo apt-get install python-libvirt libvirt-bin kvm rabbitmq-server python-dev python-pycurl python-simplejson
  wget http://www.tornadoweb.org/static/tornado-0.2.tar.gz
  tar xvzf tornado-0.2.tar.gz
  cd tornado-0.2
  python setup.py build
  sudo python setup.py install
