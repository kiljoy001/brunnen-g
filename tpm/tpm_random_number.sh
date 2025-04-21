#!/bin/bash
set -euo pipefail

# Configuration
DEFAULT_OUTPUT="./tpm_random.bin"
BYTES=32
ENGINE="tpm2tss"

# Help function
usage() {
    echo "Usage: $0 [-o output_file] [-f hex|bin] [-b bytes]"
    echo "Generate TPM-backed random numbers with OpenSSL"
    echo "Options:"
    echo "  -o  Output file path (default: ${DEFAULT_OUTPUT})"
    echo "  -f  Output format (hex or binary, default: bin)"
    echo "  -b  Number of bytes (default: ${BYTES})"
    exit 1
}

# Parse arguments
while getopts ":o:f:b:" opt; do
    case $opt in
        o) OUTPUT_FILE="$OPTARG" ;;
        f) FORMAT="$OPTARG" ;;
        b) BYTES="$OPTARG" ;;
        \?) usage ;;
    esac
done

# Set defaults
OUTPUT_FILE="${OUTPUT_FILE:-$DEFAULT_OUTPUT}"
FORMAT="${FORMAT:-bin}"

# Validate format
if [[ "$FORMAT" != "hex" && "$FORMAT" != "bin" ]]; then
    echo "ERROR: Invalid format. Use 'hex' or 'bin'"
    usage
fi

# Validate byte count
if ! [[ "$BYTES" =~ ^[0-9]+$ ]] || [ "$BYTES" -lt 1 ]; then
    echo "ERROR: Bytes must be a positive integer"
    usage
fi

# Check dependencies
check_deps() {
    command -v openssl >/dev/null 2>&1 || {
        echo "ERROR: OpenSSL not found"
        exit 1
    }
    
    if ! openssl engine "$ENGINE" &>/dev/null; then
        echo "ERROR: TPM2 engine ($ENGINE) not available in OpenSSL"
        exit 1
    fi
}

# Generate random data
generate_random() {
    local format_args=()
    
    if [[ "$FORMAT" == "hex" ]]; then
        format_args=(-hex)
    else
        format_args=(-out "$OUTPUT_FILE")
    fi

    openssl rand -engine "$ENGINE" "${format_args[@]}" "$BYTES"
    
    # Add newline for hex format
    if [[ "$FORMAT" == "hex" ]]; then
        echo >> "$OUTPUT_FILE"
    fi
}

# Main execution
main() {
    check_deps
    
    echo "Generating ${BYTES} random bytes using TPM..."
    generate_random
    
    # Set secure permissions
    chmod 600 "$OUTPUT_FILE"
    
    echo "Success: Random data saved to ${OUTPUT_FILE}"
    echo "SHA-256: $(openssl dgst -sha256 "$OUTPUT_FILE")"
}

# Run main function
main