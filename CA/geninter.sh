#!/bin/bash
mkdir INTER/$1
cd INTER/$1
cp ../../openssl.cnf.tmpl openssl.cnf
sed -i -e s/%USERNAME%/$1/g openssl.cnf
mkdir certs crl newcerts private
echo "10" > serial
touch index.txt
openssl genrsa -des3 -out private/cakey.pem 1024 -config ./openssl.cnf -batch -nodes
openssl req -new -sha1 -key private/cakey.pem -out ../../reqs/inter$1.csr -batch -subj "/C=US/ST=California/L=Moffett Field/O=NASA Ames Research Center/OU=NEBULA DEV/CN=customer-intCA-$1"
cd ../../
openssl ca -extensions v3_ca -days 365 -out INTER/$1/cacert.pem -in reqs/inter$1.csr -config openssl.cnf -batch