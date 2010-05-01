Getting Started with Nova
=========================


GOTTA HAVE A nova.pth file added or it WONT WORK (will write setup.py file soon)

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


Installation
============

    apt-get install dnsmasq python-libvirt libvirt-bin python-setuptools python-dev python-pycurl python-simplejson python-m3crypto
    apt-get install iscsitarget aoetools vblade-persist kpartx vlan

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
    iptables --table nat --append POSTROUTING --out-interface $PUBLICIFACE -j MASQUERADE

    # setup ldap (slap.sh as root will remove ldap and reinstall it)
    # run rabbitmq-server
    # start api_worker, s3_worker, node_worker, storage_worker
    # Add yourself to the libvirtd group, log out, and log back in
    # Make sure the user who will launch the workers has sudo privileges w/o pass (will fix later)