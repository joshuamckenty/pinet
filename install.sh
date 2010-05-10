#!/usr/bin/env bash
# set values and uncomment the lines below
# CC_IP=10.255.255.8
# VLAN_START=2040
# VLAN_END=2059
# PUBLIC_IPS=208.87.118.144/28
# the next four flags determine which binaries to run
ENDPOINT=1
OBJECTSTORE=1
COMPUTE=1
VOLUME=1

if [ -n "${CC_IP+x}" \
    -o -n "${VLAN_START+x}" \
    -o -n "${VLAN_END+x}" \
    -o -n "${PUBLIC_IPS+x}" ]
then
    echo "Installing Nova"
else
    echo "Please edit this script before running it"
    exit 1
fi

PUBLIC_IFACE=124
IMAGES_URL=http://snake000/nova/base-images.tar 
BRIDGE_DEV=eth2
BASE_PATH=/srv/cloud
INSTANCES_VOL_SIZE=1T
OBJECTSTORE_VOL_SIZE=1T
CC_PORT=8773
PRIVATE_IPS=10.128.0.0/12
OBJECTSTORE_HOST=$CC_IP
RABBIT_HOST=$CC_IP

OBJECTSTORE_PATH=$BASE_PATH/objectstore
CA_PATH=$BASE_PATH/CA
KEYS_PATH=$BASE_PATH/keys
DATA_PATH=$BASE_PATH/keeper
NET_PATH=$BASE_PATH/networks
INSTANCES_PATH=$BASE_PATH/instances
BUCKETS_PATH=$OBJECTSTORE_PATH/buckets
IMAGES_PATH=$OBJECTSTORE_PATH/images
ADMIN_PATH=$BASE_PATH/admin
BIN_PATH=$BASE_PATH/nova/bin

AOE_DEV=$BRIDGE_DEV
VOLUME_GROUP=vgdata
STORAGE_DEV=/dev/sdc

PTH_FILE=/usr/lib/python2.6/dist-packages/nova.pth
export DEBIAN_FRONTEND=noninteractive

mkdir /root/.ssh
mv /root/.ssh/id_rsa id_rsa.old
cat > /root/.ssh/id_rsa <<ID_RSA_EOF
-----BEGIN RSA PRIVATE KEY-----
MIIEoQIBAAKCAQEAwh2ZyLAc/qpij0yBC7oo2Mr8+aV7HJ7trfoDngfoR/GZVw0H
ZxpzmJuo9KHg2/aiXxXpLfDjcvnaW8qEaiff75x/pOUqRWocWJ9eV1OoZdOsR5r2
jHMiQABinsbwjKn3fnSc20Lz0NamQ0CesBD6ZZjJxw12W/9Cw0FwYHJOBIGCb3FY
KIiJQgVb5ilT2yGKwhVoa3tm0MXY8JvnsLB7NX96Wb9ir2ILKG3w7mH/MhOcIz32
yyVUEq0XK53RlLGpR92k+d5VNVZhdfeXFX0Y/VE6nSw2vbXRKOg5/Jo4o1UeFcPp
WZ0TrSK9jhbz9onoUIbQ773rTAVVo1MCMTJffQIBIwKCAQBeSORLiL2gRCE+SbsF
sjEY159x8Ups/LyWVN0vgC7+X2e8kUy9DNkPnBA8TqBq1uEm3sG3On0alp1Chu/b
yjmRo8j4Ug03qJFs37F6332tzTZr7C6b/WhoOrOO8und7CfBFBGsU7hA3UlxH2MF
D4+Qbshn/zl9JDZe1qRMGkMmwbdCYd1Mis/4tg+wCCpTL1lsgBgppvrj5wKxsHMz
d5Oj7GGQOXNkyL40H6CfaTYmmrkCu0ua72/79aiCxGPYp973IWYHda91ZJfAZQmE
5ZpOQ1pVLEBdKCIuzfOUuDcwytjbsQDhiQSp9gmChVi8wLifCs8svfK9317NwbiY
/xNfAoGBAN97FxOIAHzlTbx0cA1KbaffL35cHKcwi7wLMwmz6z9L3dADbPHfxmDA
AenBojTFAp1hZlRtaaVxsbarhqlZn6hJVhGH/0wV/mzPXuQNznl67gK+jCpyVyGM
J4UpMPpOKGOZcBU8eTZ7SASnJvBmOfPF2h5zTZwdIqMOzvjSxXTTAoGBAN5cn9dd
TCPzQMpwt4YDjqM/wBKqjn7aEzV3lC0LR4Rq9zvTCVYPK4w5WBbVfcRZ0nLLRvem
RzF8H7pFsABP1oE994UmRxha1CWiBOq51elZum7U6pbW3uG03HQKoq6WXez0QcM9
vnk9WKVSsEzehvDo4byn2i4+j0m/uPa6BWhvAoGADMU0hMXxZjj9ILYySeb+86Za
fD/HH38d7Xz7mieJyRpHMHU5bOg3OLqDxDbzU3j41csNKWVWfnuGf3eECa1ZlJZ5
8l+K7meoI3mQZM2WxRz3qGKo7HuP80nWX2Fwg1TsXXZ7bu2DRPEaDuT66SpptiiQ
Hv9GQ29hEKHCryH8p5cCgYA5LcKzuOexeRCpFauI3Ffg1eDu22Z4Y/ZPk8cERLqe
ZKX5cMfi7fVBUJL+jqtPv1NfWNe8Bi+QYb8EA0qDvMIhO9HvCdfEbyCb9nZK/JYX
btgrIM6b0No6Ce+LjbTNzuTzycfEfZdhASVsVxdkOTikWSQakY/gAXVNenFkA/LD
FQKBgQCQwcA+qEfP0r6jmoErbyUSyVxgEhOb13BKYm9lP8aNm42oLOYB0DOTXqiS
adz6oj6fTl2fdN5q4iE77aME0dpM/5zBYUOAe3g1PVKU0BNZQWXPobPpQZ+XTHJZ
2S5UBFGxJHo84Uql+9kxv0otyRB+mheeTyWrH9ssWwhsFKQhgA==
-----END RSA PRIVATE KEY-----
ID_RSA_EOF

cat >> /root/.ssh/known_hosts <<KNOWN_HOSTS_EOF
|1|2Otj+Sc/J2kmhMHCpaSI0o6ymIM=|Lc4HCM/1qsAnc0EZJuUTLYqvnXU= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ==
|1|4kZimi6bcqoyPthYbSg5UOAAZNE=|D33OcN9xe90J+GLYS2BCFR5uFo8= ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ==
KNOWN_HOSTS_EOF

chmod 600 /root/.ssh/id_rsa
mkdir -p $BASE_PATH
apt-get install -y git-core
git clone git@github.com:/angst/pinet $BASE_PATH
mkdir -p $KEYS_PATH
mkdir -p $CA_PATH
cd $CA_PATH
./genrootca.sh
apt-get install -y python-libvirt python-paramiko python-setuptools python-dev python-pycurl python-m2crypto python-twisted
echo $BASE_PATH | cat > $PTH_FILE
apt-get install -y libvirt-bin aoetools vlan euca2ools lsh-utils
modprobe aoe

# perhaps we shouldn't actually try to create the volume group?
pvcreate $STORAGE_DEV
vgcreate -s 32M $VOLUME_GROUP $STORAGE_DEV

cat > $BIN_PATH/nova.conf <<NOVA_CONF_EOF
--ec2_url=http://$CC_IP:$CC_PORT/services/Cloud
--rabbit_host=$RABBIT_HOST
--datastore_path=$DATA_PATH
--networks_path=$NET_PATH
--instances_path=$INSTANCES_PATH
--buckets_path=$BUCKETS_PATH
--images_path=$IMAGES_PATH
--ca_path=$CA_PATH
--keys_path=$KEYS_PATH
--vlan_start=$VLAN_START
--vlan_end=$VLAN_END
--private_range=$PRIVATE_IPS
--public_range=$PUBLIC_IPS
--s3_host=$OBJECTSTORE_HOST
--public_vlan=$PUBLIC_IFACE
--volume_group=$VOLUME_GROUP
--bridge_dev=$BRIDGE_DEV
--storage_dev=$STORAGE_DEV
--aoe_eth_dev=$AOE_DEV
--public_vlan=$PUBLIC_IFACE
--daemonize
--verbose
--undefok=rabbit_host,datastore_path,networks_path,instances_path,buckets_path,images_path,ca_path,keys_path,vlan_start,vlan_end,private_range,public_range,s3_host,public_vlan,volume_group,bridge_dev,storage_dev,aoe_eth_dev,public_vlan,daemonize,verbose
NOVA_CONF_EOF

cd $BIN_PATH

if [ $ENDPOINT -eq 1 ]; then    
$BASE_PATH/nova/auth/slap.sh
apt-get install -y rabbitmq-server dnsmasq unzip
iptables -t nat -A PREROUTING -s 0.0.0.0/0 -d 169.254.169.254/32 -p tcp -m tcp \
--dport 80 -j DNAT --to-destination $CC_IP:$CC_PORT
iptables --table nat --append POSTROUTING --out-interface vlan$PUBLIC_IFACE -j MASQUERADE
/etc/init.d/rabbitmq-server start
killall dnsmasq
mkdir -p $ADMIN_PATH
python $BASE_PATH/nova/bin/nova-manage user admin admin
python $BASE_PATH/nova/bin/nova-manage user zip admin $ADMIN_PATH/admin.zip
unzip -o -d $ADMIN_PATH $ADMIN_PATH/admin.zip

python $BIN_PATH/nova-api start
fi

if [ $OBJECTSTORE -eq 1 ]; then    
apt-get install -y nginx
lvcreate -L $OBJECTSTORE_VOL_SIZE -n objectstore $VOLUME_GROUP \
&& mkfs.ext4 /dev/mapper/$VOLUME_GROUP-objectstore
mkdir -p $OBJECTSTORE_PATH
mount /dev/mapper/$VOLUME_GROUP-objectstore $OBJECTSTORE_PATH
mkdir -p $BUCKETS_PATH
mkdir -p $IMAGES_PATH
cat > /etc/nginx/sites-enabled/default <<NGINX_SITE_EOF
server {
        listen   3333 default;
        server_name  localhost;
        client_max_body_size 10m;

        access_log  /var/log/nginx/localhost.access.log;

        location ~ /_images/.+ {
                root   $IMAGES_PATH;
                rewrite  ^/_images/(.*)\$  /\$1  break;
        }

        location / {
             proxy_pass http://localhost:3334/;
        }
}
NGINX_SITE_EOF
/etc/init.d/nginx restart
curl $IMAGES_URL | tar -C $IMAGES_PATH -xf -
python $BIN_PATH/nova-objectstore start
fi

if [ $COMPUTE -eq 1 ]; then    
apt-get install -y kpartx kvm
lvcreate -L $INSTANCES_VOL_SIZE -n instances $VOLUME_GROUP \
&& mkfs.ext4 /dev/mapper/$VOLUME_GROUP-instances
mkdir $INSTANCES_PATH
mount /dev/mapper/$VOLUME_GROUP-instances $INSTANCES_PATH
modprobe kvm_intel
/etc/init.d/libvirt-bin restart
python $BIN_PATH/nova-compute start
fi

if [ $VOLUME -eq 1 ]; then    
apt-get install -y vblade-persist
python $BIN_PATH/nova-volume start
fi

