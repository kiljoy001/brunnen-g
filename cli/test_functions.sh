#!/bin/bash

# Source main functions
source ./brunnen-cli.sh

test_user_functions() {
    echo "=== Testing User Functions ==="
    
    # Clean start
    rm -f "$DB_NAME"
    
    echo "Testing register_identity..."
    # Mock the domain verification to skip interactive parts
    verify_domain_ownership() { echo "Mocked verification: true"; return 0; }
    
    # Test with mock inputs
    echo -e "testuser\ntest.coin\nn" | register_identity
    
    echo "Testing query_user..."
    echo "testuser@test.coin" | query_user
    
    echo "Testing verify_identity..."
    echo "testuser@test.coin" | verify_identity
    
    echo "Database contents:"
    sqlite3 "$DB_NAME" "SELECT * FROM address_keys;"
}

test_user_functions