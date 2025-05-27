#!/bin/bash
#test_ipfs.sh

# Source the main functions
source ./brunnen-cli.sh

test_ipfs_integration() {
    echo "=== Testing IPFS Integration ==="
    
    # Create database with test data
    create_database
    
    # Add test records
    sqlite3 "$DB_NAME" "
    INSERT INTO address_keys (address, pubkey, TPM_enable) VALUES 
    ('test@rentonsoftworks.coin', 'testkey123', 0);
    
    INSERT INTO tpm_domain_settings (domain, TPM_enabled) VALUES 
    ('rentonsoftworks.coin', 1);
    "
    
    # Calculate merkle root
    echo "Calculating merkle root..."
    update_all_merkle_roots
    final_root=$(sqlite3 "$DB_NAME" "SELECT root FROM db_root WHERE table_name='db_root'")
    
    # Upload to IPFS
    echo "Uploading database to IPFS..."
    cid=$(upload_to_ipfs "$DB_NAME")
    
    if [[ $? -eq 0 ]]; then
        echo "Success! Ready to publish to Emercoin:"
        echo "CID: $cid"
        echo "Merkle Root: $final_root"
        
        # Optionally publish to Emercoin
        echo -n "Publish to Emercoin? (y/n): "
        read publish_choice
        if [[ "$publish_choice" == "y" ]]; then
            publish_to_emercoin "rentonsoftworks.coin" "$cid" "$final_root"
        fi
    else
        echo "IPFS upload failed"
    fi
}