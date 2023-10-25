#!/bin/bash

set -x

rm /etc/localtime
ln -s /usr/share/zoneinfo/America/Chicago /etc/localtime

apt-get update
apt-get -y install python3 python3-pip git vim tmux
pip3 install --upgrade pip
pip3 install --upgrade requests openpyxl bs4 pandas xlrd lxml python-dateutil
pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
pip3 install --upgrade twilio phonenumbers peopledatalabs
pip3 install --upgrade visidata 
pip3 install --upgrade geopy
pip3 install --upgrade paramiko

apt-get install -y gnupg software-properties-common curl
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
apt-get update
apt-get -y install terraform

curl -fsSL https://deb.nodesource.com/setup_18.x -o /tmp/install_node.sh
bash /tmp/install_node.sh
apt-get install -y gcc g++ make nodejs

npm install n8n -g
npm install pm2 -g
npm install frontail -g

curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh > /tmp/install.sh && bash /tmp/install.sh
dolt config --global --add user.email noreply@keyspace.lt
dolt config --global --add user.name "ChicagoCrashes automation"

mkdir /root/data
mkdir /root/data/ChicagoCrashes
pushd /root/data/ChicagoCrashes || exit
dolt init
echo "CREATE TABLE accident (rd TEXT PRIMARY KEY, date DATE, address TEXT, scraped_at TIMESTAMP);" |  dolt sql 
echo "CREATE TABLE unit (rd TEXT, unit_no INT, driver_name TEXT, driver_phone TEXT, driver_addr TEXT, insurance TEXT, owner_name TEXT, owner_addr TEXT, scraped_at TIMESTAMP);" | dolt sql

echo "CREATE TABLE stats (started_at TIMESTAMP PRIMARY KEY, finished_at TIMESTAMP, ref_rd TEXT, try_next INT, try_prev INT);" | dolt sql
dolt add .
dolt commit -m "Create tables"
popd || exit

pip3 install doltpy

{
    echo "TZ=America/Chicago" 
    echo "GENERIC_TIMEZONE=America/Chicago" 
    echo "N8N_PERSONALIZATION_ENABLED=false" 
    echo "N8N_BASIC_AUTH_ACTIVE=true" 
    echo "N8N_BASIC_AUTH_USER=user"
    echo "N8N_BASIC_AUTH_PASSWORD=HYOfbhgA6MpUJpEXgbHULfTw" 
    echo "N8N_USER_MANAGEMENT_DISABLED=true"
} >> /etc/environment

export TZ=America/Chicago
export GENERIC_TIMEZONE=America/Chicago
export N8N_PERSONALIZATION_ENABLED=false
export N8N_BASIC_AUTH_ACTIVE=true
export N8N_BASIC_AUTH_USER=user
export N8N_BASIC_AUTH_PASSWORD=HYOfbhgA6MpUJpEXgbHULfTw
export N8N_USER_MANAGEMENT_DISABLED=true

pm2 start n8n
pm2 start --name frontail-scrape frontail -- --user user --password HYOfbhgA6MpUJpEXgbHULfTw --port 9002 /root/src/scrape.log
pm2 start --name frontail-send frontail -- --user user --password HYOfbhgA6MpUJpEXgbHULfTw --port 9003 /root/src/upload.log /root/src/send_sms.log /root/src/send_clean.log
pm2 save
pm2 startup systemd
