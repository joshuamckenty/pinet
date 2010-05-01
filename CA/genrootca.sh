#!/bin/bash
 openssl req -new -x509 -extensions v3_ca -keyout private/cakey.pem -out cacert.pem -days 365 -config ./openssl.cnf -batch -nodes
touch index.txt
echo "10" > serial

