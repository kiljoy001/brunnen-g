#!/bin/bash
# Path to TPM key files
PRIMARY_HANDLE=0x81000001
KEY_HANDLE=0x81000002
CONFIG_PATH="/etc/yggdrasil/yggdrasil.conf"
TEMP_KEY_FILE=$(mktemp)
chmod 600 $TEMP_KEY_FILE

# Check if persistent handles exist
if tpm2_getcap handles-persistent | grep -q "$PRIMARY_HANDLE"; then
  echo "Found existing TPM handles, loading keys..."
else
  echo "No persistent handles found, creating new TPM keys..."
  # Create primary key
  tpm2_createprimary -C o -g sha256 -G ecc -c primary.ctx
  tpm2_evictcontrol -C o -c primary.ctx $PRIMARY_HANDLE
  
  # Generate Yggdrasil config with a new key
  yggdrasil -genconf > $CONFIG_PATH.new
  YGG_KEY=$(grep PrivateKey $CONFIG_PATH.new | awk '{print $2}')
  
  # Create a sealed object with the Yggdrasil key
  echo -n "$YGG_KEY" | tpm2_create -C $PRIMARY_HANDLE -i- -u key.pub -r key.priv
  tpm2_load -C $PRIMARY_HANDLE -u key.pub -r key.priv -c key.ctx
  tpm2_evictcontrol -C o -c key.ctx $KEY_HANDLE
  
  # Use the newly generated config for first boot
  mv $CONFIG_PATH.new $CONFIG_PATH
  echo "New Yggdrasil identity created and sealed in TPM"
fi

# For subsequent boots, unseal and use the existing key
if [ -f "$CONFIG_PATH" ]; then
  # Generate a default config as template
  yggdrasil -genconf > $CONFIG_PATH.template
  
  # Unseal the key from TPM
  tpm2_unseal -c $KEY_HANDLE > $TEMP_KEY_FILE
  
  # Update the config with our persistent key
  PRIVATE_KEY=$(cat $TEMP_KEY_FILE)
  sed "s/PrivateKey: .*$/PrivateKey: $PRIVATE_KEY/" $CONFIG_PATH.template > $CONFIG_PATH
  
  # Securely remove the temporary key file
  shred -u $TEMP_KEY_FILE
  rm -f $CONFIG_PATH.template
  
  echo "Configured Yggdrasil with TPM-protected key"
fi

# Start Yggdrasil
echo "Starting Yggdrasil..."
/usr/local/bin/yggdrasil -useconffile $CONFIG_PATH &