NOVA
=====

Docs for this project are now generated in Sphinx, and will shortly be hosted on the project page.


an amazon/eucalyptus/rackspace cloud clone in python, amqp, tornado, ...

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
    [X] Deliver creds to user (novarc, x509, ...)
    [X] users exist and have ec2 credentials
    [X] user can create and destroy keypairs

Instances
---------

    [x] euca-run-instances requests nodes to spawn instances
    [ ] can only launch images that user owns or is public
    [x] keypair is added when running instance
    [ ] nodes have a quota on # of instances
    [X] can allocate and attach public IPs
    [X] network state persists
    [x] each user gets a subnet and vlan for their instances
    [x] node downloads proper image from S3 (verify image via content-md5)
    [x] instances can access their user-data, meta-data
    [X] hard code all instances for a user into "default" security group: deny except 22, 80, 443, and 1194
    [x] instances state from multiple nodes overwrite each other (update_state code)
    [x] euca-get-console-output works
    [x] euca-terminate-instances works
    [X] euca-run-instances uses userdata, instance size, image, keypair, ... (all api params)
    [X] euca-describe-instances works
    [x] euca-describe-instances only returns instances I have permissions to
    [x] can launch from many different images
    [x] ignore kernel/ramdisk from user, hardcode for now
    [x] can launch different sizes
    [X] NAT to public internet works from instances
    [ ] access to other users instances only works on "default" protocols
    [X] terminate should send to only the approriate node
    [X] BUG: running -n N+1 instances when you have N results in only N instances launched
        - seems to be an issue with multiprocess.Process
        the _launch call doesn't occur when two Processes are running at the same time
        INFO:root:Done create image for: i-286573
        DEBUG:root:Arrived in _launch, thanks to callback on deferred. <- only happens first time
    [X] BUG: launching multiple instances show the incorrect IP in describe-instance during while pending
    [x] describe-instances doesn't show public ips
    [ ] When instances are shutdown or terminated, clean them up (detach IP and volume)

S3 / Images
-----------

    [x] euca-upload-bundle: buckets have owners and are private (only accessible by owner and admin)
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

    [X] s3server's register decryption should be done in bkg:
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
    [ ] node/node_worker is bad name for instances node as storage is a node too
    [ ] describe instances should be returned ordered by ami_launch_index
    [ ] multiprocess the cloud for x509 generation
    [ ] bin/users.py uses command line flags
    [ ] more space for instance ids
    [ ] get Dean to update switch configuration
    [ ] BUG: cloud using boto to communicate with OSS means that if OSS throws a
        500 in response to the error it will lock up the cloud by doing time.sleep
        and retrying for about a minute (5 times, the delay doubling each time)

Nasa Deploy
-----------

    [X] Port existing users, images from euca
    [X] Port cloudpipe and dashboard, install them
    [ ] Remove secgroups from dashboard UI
    [ ] Configure instance sizes


Optimizations
-------------

    [X] dd warns blocksize of 512 is slow in partition2disk.convert
    [ ] tiny (5x overcommitted CPU) shouldn't be on same nodes as regular sizes
    [ ] lvm instead of file based disk images?
    [ ] decrypt in python is slow!


Future
------

    [ ] users have quotas
    [ ] fix fingerprint generation on creation of keypair
    [ ] api to modify private/public (image attributes) works
    [ ] proper security groups
    [ ] projects / groups
    [ ] RBAC - roles based control
    [ ] on cloud launch, it should broadcast to nodes to report their current state
    [ ] throttling for reporting state from node/storage/...
        (report back at least every minute, at most once a second, only when things change)
    [ ] support for ephemeral and swap on disk image generation
    [ ] windows support
    [ ] out-of-band console - example for XEN: http://nostarch.com/xen.htm and
        http://book.xen.prgmr.com/mediawiki/index.php/Prgmr_menu

