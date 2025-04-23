# Use fedora 41 as the base image
FROM fedora:41

# Copy installation scripts
COPY install_rabbitmq.sh /tmp/
COPY install_yggdrasil.sh /tmp/
RUN chmod +x /tmp/install_yggdrasil.sh /tmp/install_rabbitmq.sh

# Install dependencies
RUN dnf install -y tpm2-tss tpm2-tss-fapi python3-pip pkg-config tpm2-tss-devel \
    python3-devel swtpm tpm2-abrmd dbus-daemon nmap-ncat tpm2-tss-engine openssl tpm2-openssl tpm2-tools \
    glibc-langpack-en glibc-locale-source \
    golang git make \
    @development-tools

# Run installation scripts during build
RUN /tmp/install_yggdrasil.sh && \
    /tmp/install_rabbitmq.sh && \
    rm -f /tmp/install_yggdrasil.sh /tmp/install_rabbitmq.sh

# Configure locale
RUN localedef -c -i en_US -f UTF-8 en_US.UTF-8
RUN dnf clean all

# Configure Yggdrasil for multicast discovery
RUN sed -i 's/MulticastInterfaces: \[\]/MulticastInterfaces: \[\n    {\n      Regex: "^eth"\n      Beacon: true\n      Listen: true\n      Port: 9001\n      Priority: 0\n    }\n  \]/' /etc/yggdrasil/yggdrasil.conf

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PYTHONIOENCODING=UTF-8

# Install tpm2-pytss (Python bindings) & Pipenv
RUN pip3 install tpm2-pytss pipenv

# Copy config file for abrmd to container
COPY tpm2-abrmd.conf /etc/dbus-1/system.d/

# Create a directory for your code
WORKDIR /tpm
COPY tpm /tpm
COPY Pipfile /tpm
COPY Pipfile.lock /tpm
COPY tests /tests

# Set python path to root
ENV PYTHONPATH=/

# Yggdrasil presistant key script
COPY yggdrasil-tpm-startup.sh /usr/local/bin
RUN chmod +x /usr/local/bin/yggdrasil-tpm-startup.sh

# Install dependancies
RUN pipenv install Pipfile --deploy --ignore-pipfile

# Copy and modify the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]