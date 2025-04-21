#!/bin/bash

# Install RabbitMQ for Fedora-based containers
dnf install -y curl socat

# Install Erlang first
curl -s https://packagecloud.io/install/repositories/rabbitmq/erlang/script.rpm.sh | bash
dnf install -y erlang

# Then install RabbitMQ
curl -s https://packagecloud.io/install/repositories/rabbitmq/rabbitmq-server/script.rpm.sh | bash
dnf install -y rabbitmq-server

# Configure for container use
mkdir -p /etc/rabbitmq
echo "NODENAME=rabbit@localhost" > /etc/rabbitmq/rabbitmq-env.conf
echo "LOG_BASE=/var/log/rabbitmq" >> /etc/rabbitmq/rabbitmq-env.conf
mkdir -p /var/log/rabbitmq/