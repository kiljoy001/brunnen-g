#!/bin/bash

source ./tpm/tpm_provisioning.sh
source ./tpm/tpm_random_number.sh
source ./tpm/tpm_self_signed_cert.sh

# DGA database naming
generate_db_name() {
    local seed=$(hostname)$(whoami)
    local hash=$(echo "$seed" | sha256sum | cut -c1-12)
    echo "${hash}.tmp"
}

DB_NAME=$(generate_db_name)

tpm_menu() {
    echo "=== TPM Operations ==="
    echo "1) Generate TPM Certificate"
    echo "2) Generate Random Data"
    echo "3) Provision TPM Keys"
    echo -n "Choice: "
    read tmp_choice
    
    case $tmp_choice in
        1) ../tpm/tpm_self_signed_cert.sh ;;
        2) ../tpm/tpm_random_number.sh -f hex ;;
        3) ../tpm/tpm_provisioning.sh ;;
    esac
}

# create_database - builds the distribuited database that holds public key data
create_database() {
    sqlite3 $DB_NAME "
    CREATE TABLE IF NOT EXISTS address_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        address TEXT NOT NULL,
        pubkey TEXT NOT NULL,
        TPM_key TEXT,
        TPM_key_hash BLOB,
        TPM_enable BOOLEAN DEFAULT 0,
        row_hash BLOB
        );
    
    CREATE TABLE IF NOT EXISTS db_root (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        root BLOB NOT NULL,
        row_hash BLOB
    );

    CREATE TABLE IF NOT EXISTS tpm_domain_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        TPM_enable BOOLEAN DEFAULT 0,
        row_hash BLOB
    );
    "
    echo "Database created: $DB_NAME"
}

verify_domain_ownership() {
    local domain=$1
    
    domain_info=$(emercoin-cli name_show "dns:$domain" 2>&1)
    if [[ $? -ne 0 ]]; then
        echo "Domain not found on blockchain"
        return 1
    fi
    
    echo "Domain found: $domain"
    
    # List wallets
    wallets=$(emercoin-cli listwallets | jq -r '.[]')
    echo "Available wallets:"
    IFS=$'\n' read -rd '' -a wallet_array <<< "$wallets"
    
    for i in "${!wallet_array[@]}"; do
        echo "$((i+1))) ${wallet_array[i]}"
    done
    
    echo -n "Select wallet: "
    read wallet_choice
    selected_wallet="${wallet_array[$((wallet_choice-1))]}"
    
    echo -n "Enter domain owner address: "
    read domain_address
    
    # Check if wallet is encrypted
    wallet_info=$(emercoin-cli -rpcwallet="$selected_wallet" getwalletinfo 2>&1)
    if echo "$wallet_info" | grep -q '"unlocked_until": 0'; then
        echo -n "Wallet locked. Enter passphrase: "
        read -s passphrase
        echo
        emercoin-cli -rpcwallet="$selected_wallet" walletpassphrase "$passphrase" 60
    fi
    
    # Generate and sign challenge
    challenge=$(openssl rand -hex 32)
    echo "Challenge: $challenge"
    
    signature=$(emercoin-cli -rpcwallet="$selected_wallet" signmessage "$domain_address" "$challenge")
    if [[ $? -eq 0 ]]; then
        echo "Domain ownership verified"
        return 0
    else
        echo "Signature failed"
        return 1
    fi
}
calculate_row_hash() {
    local table=$1
    local id=$2
    
    case $table in
        "address_keys")
            row_data=$(sqlite3 "$DB_NAME" "SELECT address || '|' || pubkey || '|' || COALESCE(TPM_key,'') || '|' || COALESCE(TPM_key_hash,'') || '|' || TPM_enable FROM address_keys WHERE id = $id")
            row_hash=$(echo -n "$row_data" | sha256sum | cut -d' ' -f1)
            sqlite3 "$DB_NAME" "UPDATE address_keys SET row_hash = '$row_hash' WHERE id = $id"
            ;;
        "tmp_domain_settings")
            row_data=$(sqlite3 "$DB_NAME" "SELECT domain || '|' || TPM_enabled FROM tmp_domain_settings WHERE id = $id")
            row_hash=$(echo -n "$row_data" | sha256sum | cut -d' ' -f1)
            sqlite3 "$DB_NAME" "UPDATE tpm_domain_settings SET row_hash = '$row_hash' WHERE id = $id"
            ;;
        "db_root")
            row_data=$(sqlite3 "$DB_NAME" "SELECT table_name || '|' || hex(root) FROM db_root WHERE id = $id")
            row_hash=$(echo -n "$row_data" | sha256sum | cut -d' ' -f1)
            sqlite3 "$DB_NAME" "UPDATE db_root SET row_hash = '$row_hash' WHERE id = $id"
            ;;
    esac
}

build_table_merkle() {
    local table=$1
    local temp_file="/dev/shm/hashes_$$"
    
    sqlite3 "$DB_NAME" "SELECT row_hash FROM $table ORDER BY id;" > "$temp_file"
    
    while [ $(wc -l < "$temp_file") -gt 1 ]; do
        if [ $(($(wc -l < "$temp_file") % 2)) -eq 1 ]; then
            tail -1 "$temp_file" >> "$temp_file"
        fi
        
        awk 'NR%2==1{h1=$0; getline h2; print h1 h2}' "$temp_file" | \
        while read combined; do
            echo -n "$combined" | sha256sum | cut -d' ' -f1
        done > "${temp_file}.new"
        
        mv "${temp_file}.new" "$temp_file"
    done
    
    merkle_root=$(cat "$temp_file")
    shred -u "$temp_file"
    
    sqlite3 "$DB_NAME" "INSERT OR REPLACE INTO db_root (table_name, root) VALUES ('$table', '$merkle_root')"
    echo "$merkle_root"
}

update_all_merkle_roots() {
    sqlite3 "$DB_NAME" "DELETE FROM db_root"
    
    sqlite3 "$DB_NAME" "SELECT id FROM address_keys;" | while read id; do
        calculate_row_hash "address_keys" "$id"
    done
    
    sqlite3 "$DB_NAME" "SELECT id FROM tpm_domain_settings;" | while read id; do
        calculate_row_hash "tpm_domain_settings" "$id"
    done
    
    build_table_merkle "address_keys"
    build_table_merkle "tpm_domain_settings"
    
    sqlite3 "$DB_NAME" "SELECT id FROM db_root;" | while read id; do 
         calculate_row_hash "db_root" "$id"
    done

    build_table_merkle "db_root"
    
    final_root=$(sqlite3 "$DB_NAME" "SELECT root FROM db_root WHERE table_name='db_root'")
    echo "Final merkle root: $final_root"
}

publish_to_emercoin() {
    local domain="$1"
    local cid="$2" 
    local merkle_root="$3"
    
    # Create JSON with both values
    json_data="{\"cid\":\"$cid\",\"merkle_root\":\"$merkle_root\"}"
    
    echo "Publishing to Emercoin NVS..."
    echo "Domain: dns:$domain"
    echo "Data: $json_data"
    
    # Update NVS record (requires domain ownership verification)
    if verify_domain_ownership "$domain"; then
        emercoin-cli -rpcwallet="$selected_wallet" name_update "dns:$domain" "$json_data" 365
        echo "Published to blockchain successfully"
    else
        echo "Domain ownership verification failed"
        return 1
    fi
}

register_identity() {
    echo "=== Register Identity ==="
    echo -n "Username: "
    read username
    echo -n "Domain: "
    read domain
    
    # Verify domain ownership
    if ! verify_domain_ownership "$domain"; then
        echo "Domain ownership verification failed"
        return 1
    fi
    
    address="${username}@${domain}"
    
    # Generate keypair
    echo "Generating keypair..."
    openssl genpkey -algorithm Ed25519 -out /tmp/private.pem
    openssl pkey -in /tmp/private.pem -pubout -out /tmp/public.pem
    pubkey=$(openssl pkey -in /tmp/public.pem -pubin -text -noout | grep -A5 "pub:" | tail -n +2 | tr -d ' \n:')
    
    # TPM optional
    echo -n "Enable TPM? (y/n): "
    read tmp_choice
    if [[ "$tmp_choice" == "y" ]]; then
        if ./tpm/tpm_provisioning.sh; then
            tmp_enable=1
            tmp_handle=$(cat handle.txt)
            tmp_key=$(cat signing_key.pem | base64 -w 0)
            tmp_key_hash=$(echo -n "$tmp_key" | sha256sum | cut -d' ' -f1)
        else
            echo "TPM setup failed"
            tmp_enable=0
        fi
    fi
    
    # Create database if it doesn't exist
    create_database
    
    # Insert to database
    sqlite3 "$DB_NAME" "INSERT INTO address_keys (address, pubkey, TPM_key, TPM_key_hash, TPM_enable) 
                       VALUES ('$address', '$pubkey', '$tmp_key', '$tmp_key_hash', $tmp_enable);"
    
    echo "Identity registered: $address"
    shred -u /tmp/private.pem /tmp/public.pem
}

query_user() {
    echo "=== Query User ==="
    echo -n "Enter user@domain.coin: "
    read user_address
    
    # Check local database first
    result=$(sqlite3 "$DB_NAME" "SELECT pubkey FROM address_keys WHERE address = '$user_address';" 2>/dev/null)
    
    if [[ -n "$result" ]]; then
        echo "User found locally:"
        echo "Address: $user_address"
        echo "Public Key: $result"
    else
        echo "User not found in local database"
        # TODO: Download from IPFS via domain lookup
    fi
}

verify_identity() {
    echo "=== Verify Identity ==="
    echo -n "Enter user@domain.coin: "
    read user_address
    
    # Check if user exists
    result=$(sqlite3 "$DB_NAME" "SELECT address, pubkey, TPM_enable FROM address_keys WHERE address = '$user_address';" 2>/dev/null)
    
    if [[ -n "$result" ]]; then
        echo "✅ Identity verified"
        echo "Address: $user_address"
        echo "Found in database"
        # TODO: Add merkle proof verification
    else
        echo "❌ Identity not found"
        return 1
    fi
}
echo "
██████╗ ██████╗ ██╗   ██╗███╗   ██╗███╗   ██╗███████╗███╗   ██╗       ██████╗ 
██╔══██╗██╔══██╗██║   ██║████╗  ██║████╗  ██║██╔════╝████╗  ██║      ██╔════╝ 
██████╔╝██████╔╝██║   ██║██╔██╗ ██║██╔██╗ ██║█████╗  ██╔██╗ ██║█████╗██║  ███╗
██╔══██╗██╔══██╗██║   ██║██║╚██╗██║██║╚██╗██║██╔══╝  ██║╚██╗██║╚════╝██║   ██║
██████╔╝██║  ██║╚██████╔╝██║ ╚████║██║ ╚████║███████╗██║ ╚████║      ╚██████╔╝
╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═══╝       ╚═════╝ 
                        Decentralized PKI Infrastructure
"

while true; do
    echo "=== Main Menu ==="
    echo "1) Register identity"
    echo "2) Query user@domain.coin"
    echo "3) Verify Identity"
    echo "4) Exit"
    echo "5) TPM Operations"
    echo -n "Choice: "
    
    read choice

    case $choice in
        1) register_identity ;;
        2) query_user ;;
        3) verify_identity ;;
        4) exit 0 ;;
        5) tpm_menu ;;
        *) echo "Invalid option" ;;
    esac
    echo
done

