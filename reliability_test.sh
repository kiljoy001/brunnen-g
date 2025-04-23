#!/bin/bash

LOG_FILE="tpm_reliability_test_$(date +%Y%m%d_%H%M%S).log"
TEST_LOGS_DIR="./test_logs"
CONTAINER_IMAGE="kiljoy001/brunnen-g:dev-latest"
ITERATIONS=1000  # Long-term reliability test
COOLDOWN_TIME=30  # Longer cooldown between tests

# Create log directory only
mkdir -p "$TEST_LOGS_DIR"

# Header for log file
echo "Timestamp,Iteration,YggdrasilAddress,TPMStatus,ContainerStatus" > "$LOG_FILE"

# Function to ensure orderly container shutdown
graceful_container_shutdown() {
    local container_id=$1
    local iteration=$2
    
    echo "Gracefully stopping container..."
    
    # Try to cleanly shut down Yggdrasil first if possible
    docker exec -i "$container_id" bash -c "yggdrasilctl stop" &>/dev/null || true
    sleep 5
    
    # Then stop the container
    docker stop -t 15 "$container_id" &>/dev/null
    sleep 5
    
    # Remove the container
    docker rm "$container_id" &>/dev/null
    
    echo "Container shutdown complete, waiting $COOLDOWN_TIME seconds for TPM resources to be released..."
    sleep $COOLDOWN_TIME
}

# Function to check TPM status
check_tpm_status() {
    local container_id=$1
    
    # Check TPM status
    tpm_status=$(docker exec -i "$container_id" bash -c "tpm2_getcap handles-persistent 2>&1" || echo "TPM_ERROR")
    
    # Save TPM status to log
    echo "$tpm_status" > "$TEST_LOGS_DIR/tpm_status_$iteration.log"
    
    # Check for error indicators
    if echo "$tpm_status" | grep -q "ERROR\|failed\|lockout"; then
        echo "WARNING: Potential TPM issues detected"
        return 1
    fi
    
    return 0
}

# Function to test container
test_container() {
    local iteration=$1
    local container_id=""
    
    echo "============================================="
    echo "Iteration $iteration of $ITERATIONS ($(date))"
    echo "============================================="
    
    # Longer wait before starting a new container
    echo "Pre-container startup cooldown period..."
    sleep 10
    
    echo "Starting container..."
    # Generate a unique container ID for this run
    container_id=$(docker run -it -d \
        -e DEV_MODE=1 \
        --cap-add=NET_ADMIN \
        --cap-add=NET_RAW \
        --device=/dev/net/tun:/dev/net/tun \
        --network host \
        -v ./tpmdata:/tpmdata \
        -v ./tpm-start:/var/lib/tpm \
        $CONTAINER_IMAGE)
    
    if [ -z "$container_id" ]; then
        echo "Failed to start container"
        echo "$(date +"%Y-%m-%d %H:%M:%S"),$iteration,NONE,FAILED_START,Container Failed" | tee -a "$LOG_FILE"
        return 1
    fi
    
    echo "Container started with ID: $container_id"
    
    # Longer initialization wait
    echo "Waiting for container to initialize (30s)..."
    sleep 30
    
    # Check if container is still running
    if ! docker ps -q --filter "id=$container_id" &>/dev/null; then
        echo "Container exited prematurely"
        docker logs "$container_id" > "$TEST_LOGS_DIR/failed_container_$iteration.log" 2>&1
        docker rm "$container_id" &>/dev/null || true
        echo "$(date +"%Y-%m-%d %H:%M:%S"),$iteration,NONE,UNKNOWN,Container Exited" | tee -a "$LOG_FILE"
        return 1
    fi
    
    # Save the complete yggdrasil output for debugging
    docker exec -i "$container_id" bash -c "yggdrasilctl getSelf" > "$TEST_LOGS_DIR/yggdrasil_output_$iteration.log" 2>&1
    
    # Check TPM status
    tpm_ok=1
    check_tpm_status "$container_id" || tpm_ok=0
    
    if [ $tpm_ok -eq 0 ]; then
        tpm_status="TPM_WARNING"
    else
        tpm_status="TPM_OK"
    fi
    
    # Extract Yggdrasil address
    address=$(docker exec -i "$container_id" bash -c "yggdrasilctl getSelf | grep -oE '200:[a-f0-9:]+'" || echo "ADDRESS_ERROR")
    
    if [ -z "$address" ] || [ "$address" = "ADDRESS_ERROR" ]; then
        address=$(docker exec -i "$container_id" bash -c "ip -6 addr show | grep -oE '200:[a-f0-9:]+'" || echo "ADDRESS_ERROR")
    fi
    
    if [ -z "$address" ] || [ "$address" = "ADDRESS_ERROR" ]; then
        address="NO_VALID_ADDRESS"
    fi
    
    # Log container logs
    docker logs "$container_id" > "$TEST_LOGS_DIR/container_logs_$iteration.log" 2>&1
    
    # Capture TPM-related files and permissions if they exist
    docker exec -i "$container_id" bash -c "ls -la /tpmdata/" > "$TEST_LOGS_DIR/tpmdata_files_$iteration.log" 2>&1 || true
    
    # Output with proper comma escaping for CSV
    echo "$(date +"%Y-%m-%d %H:%M:%S"),$iteration,\"$address\",$tpm_status,Running" | tee -a "$LOG_FILE"
    
    # Orderly shutdown
    graceful_container_shutdown "$container_id" "$iteration"
    
    return 0
}

echo "Starting TPM reliability testing for $ITERATIONS iterations..."
echo "This test will run for approximately $((ITERATIONS * (COOLDOWN_TIME + 60) / 60)) hours"
echo "Results will be saved to $LOG_FILE"

for i in $(seq 1 $ITERATIONS); do
    test_container $i
    
    # Stop testing if we see multiple consecutive failures indicating a lockout
    if [ $i -gt 3 ]; then
        failures=$(tail -3 "$LOG_FILE" | grep -c "TPM_WARNING\|ADDRESS_ERROR\|NO_VALID_ADDRESS")
        if [ $failures -ge 3 ]; then
            echo "WARNING: 3 consecutive failures detected, possible TPM lockout. Pausing test."
            echo "Resume test manually when TPM is available again."
            break
        fi
    fi
done

# Analyze results
echo "Test completed or paused. Analyzing results..."
total_runs=$(tail -n +2 "$LOG_FILE" | grep -c ",")
successful=$(grep -E ',"200:[a-f0-9:]+",TPM_OK' "$LOG_FILE" | wc -l) 
echo "Successful runs with Yggdrasil address: $successful out of $total_runs"

if [ $successful -gt 0 ]; then
    unique_addresses=$(grep -E ',"200:[a-f0-9:]+",TPM_OK' "$LOG_FILE" | sed -E 's/.*,"(200:[a-f0-9:]+)".*/\1/' | sort | uniq -c)
    echo "Unique Yggdrasil addresses found:"
    echo "$unique_addresses"
fi

echo "Container logs saved to $TEST_LOGS_DIR/"
echo "View complete results in $LOG_FILE"