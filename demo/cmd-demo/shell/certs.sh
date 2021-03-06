rm -rf certs/
mkdir -p certs/
cd certs/
# 设置docker的服务名
export DORY_DOCKER_NAME=docker
# 设置docker所在的名字空间
export DORY_DOCKER_NAMESPACE=dory

openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -sha512 -days 3650 -subj "/CN=${DORY_DOCKER_NAME}" -key ca.key -out ca.crt
openssl genrsa -out tls.key 4096
openssl req -sha512 -new -subj "/CN=${DORY_DOCKER_NAME}" -key tls.key -out tls.csr
cat << EOF > v3.ext
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names

[alt_names]
DNS.1=${DORY_DOCKER_NAME}
DNS.2=*.${DORY_DOCKER_NAME}
DNS.3=*.${DORY_DOCKER_NAME}.${DORY_DOCKER_NAMESPACE}
DNS.4=localhost
EOF
openssl x509 -req -sha512 -days 3650 -extfile v3.ext -CA ca.crt -CAkey ca.key -CAcreateserial -in tls.csr -out tls.crt
# openssl x509 -noout -text -in tls.crt
ping -c 3 www.baidu.com
set
cd ..
# rm -rf certs
