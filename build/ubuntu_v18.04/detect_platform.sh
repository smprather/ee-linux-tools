#!/bin/bash
# Must be sourced, not executed
# Returns 0 if platform matches, 1 otherwise
#
# For some reason, the Centos 7 version of GLIBC, 2.17, is able to execute
# The binaries built with Ubuntu 18.04, so the minimum required GLIBC is 2.17.

# Check GLIBC version
# Ubuntu 18.04 is 2.27)
# Centos 7 is 2.17
# 2.17 <= GLIBC <= 2.27 should use this platform
GLIBC_VERSION=$(ldd --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
if [[ -z "$GLIBC_VERSION" ]]; then
    return 1
fi

# Compare using bash arithmetic (avoid bc dependency)
MIN_MAJOR=2
MIN_MINOR=17
MAX_MAJOR=2
MAX_MINOR=27
DETECTED_MAJOR=$(echo "$GLIBC_VERSION" | cut -d. -f1)
DETECTED_MINOR=$(echo "$GLIBC_VERSION" | cut -d. -f2)

if [[ $DETECTED_MAJOR -lt $MIN_MAJOR ]]; then
    return 1
elif [[ $DETECTED_MAJOR -gt $MAX_MAJOR ]]; then
    return 1
elif [[ $DETECTED_MAJOR -eq $REQUIRED_MAJOR && $DETECTED_MINOR -lt $MIN_MINOR ]]; then
    return 1
elif [[ $DETECTED_MAJOR -eq $REQUIRED_MAJOR && $DETECTED_MINOR -gt $MAX_MINOR ]]; then
    return 1
fi

# Additional checks can be added here:
# - OS type (Linux, BSD, etc.)
# - Architecture (x86_64, aarch64, etc.)
# - Specific library availability

return 0
