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

Todos
====

General
-------

    [X] generate cloud cert on run if it doesn't already exist (used for bundling)
    [X] api calls are validated and ran as a user

Users
-----

    [X] X509 certs for users
    [x] add concept of admin
    [X] Deliver creds to user (pinetrc, x509, ...)
    [X] users exist and have ec2 credentials
    [X] user can create and destroy keypairs

Instances
---------

    [x] euca-run-instances requests nodes to spawn instances
    [ ] can only run instances that user owns or is public
    [x] keypair is added when running instance
    [ ] nodes have a quota on # of instances
    [ ] can allocate and attach public IPs
    [ ] network state persists
    [x] each user gets a subnet and vlan for their instances
    [ ] node downloads proper image from S3 (veyarify image via content-md5)
    [ ] instances can access their user-data, meta-data
    [ ] hard code all instances for a user into 1 security group: deny except 22, 80, 443, and 1194
    [x] euca-get-console-output works
    [x] euca-terminate-instances works
    [X] euca-run-instances uses userdata, instance size, image, keypair, ... (all api params)
    [X] euca-describe-instances works
    [x] euca-describe-instances only returns instances I have permissions to
    [x] can launch from many different images
    [ ] ignore kernel/ramdisk from user, hardcode for now
    [ ] can launch different sizes

S3 / Images
-----------

    [ ] euca-upload-bundle: buckets have owners and are private (only accessible by owner and admin)
    [x] euca-register: registration works and decrypts image with cloud's cert
    [x] euca-describe-images: returns only images that user has access to (public or theirs)
    [x] images are owned by user, and private by default

Volumes
-------

    [X] can create volumes
    [X] can destroy volumes
    [X] can attach volumes
    [ ] detach on destroy?

Cleanup
-------

    [ ] build debs - perhaps use git-buildpackage?
    [ ] remove eucalyptus specific terminology in favor of amazon (emi -> ami, ?)
    [ ] documentation/SOPs for backup, updating, ?
    [ ] add license headers - apache license
    [ ] rewrite code such as partition2disk that is too close to eucalyptus
    [ ] review code for internal (nasa) info 
    [ ] init.d scripts & location for configuration files
    [ ] Logging clean-up: system should (default?) to using syslog
    [ ] verify user is allowed to execute commands - for each API method!
    [ ] when instances are terminated, IP addresses are reclaimed


Nasa Deploy
-----------

    [ ] Port existing users, images from euca
    [ ] Port cloudpipe and dashboard, install them
    [ ] Remove secgroups from dashboard UI


Optimizations
-------------

    [ ] dd warns blocksize of 512 is slow in partition2disk.convert
    [ ] tiny (5x overcommitted CPU) shouldn't be on same nodes as regular sizes
    [ ] lvm instead of file based disk images?


Future
------

    [ ] users have quotas
    [ ] fix fingerprint generation on creation of keypair
    [ ] api to modify private/public (image attributes) works
    [ ] proper security groups
    [ ] projects / groups
    [ ] RBAC - roles based control
    [ ] throttling for reporting state from node/storage/... 
        (report back at least every minute, at most once a second, only when things change)
    [ ] support for ephemeral and swap on disk image generation
    [ ] windows support
    [ ] out-of-band console - example for XEN: http://nostarch.com/xen.htm and 
        http://book.xen.prgmr.com/mediawiki/index.php/Prgmr_menu

Installation
============

    apt-get install dnsmasq python-libvirt libvirt-bin python-setuptools python-dev python-pycurl python-simplejson python-m3crypto
    apt-get install iscsitarget aoetools vblade-persist kpartx

    # ON THE CLOUD CONTROLLER
    apt-get install rabbitmq-server 

    # ON VOLUME NODE:
    apt-get install vblade-persist aoetools

    # ON THE COMPUTE NODE:
    apt-get install aoetools kpartx kvm

    # optional packages
    apt-get install euca2ools 

    # PYTHON libraries
    easy_install twisted m2crypto

    # fix ec2 metadata/userdata uri - where $IP is the IP of the cloud
    iptables -t nat -A PREROUTING -s 0.0.0.0/0 -d 169.254.169.254/32 -p tcp -m tcp --dport 80 -j DNAT --to-destination $IP:8773

    # setup ldap (slap.sh as root will remove ldap and reinstall it)
    # run rabbitmq-server
    # start api_worker, s3_worker, node_worker, storage_worker
    # Add yourself to the libvirtd group, log out, and log back in
    # Make sure the user who will launch the workers has sudo privileges w/o pass (will fix later)
