#!/bin/bash
# Must be sourced, not executed
# Returns 0 if platform matches, 1 otherwise

# Check GLIBC version (Ubuntu 18.04 requires >= 2.27)
GLIBC_VERSION=$(ldd --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
if [[ -z "$GLIBC_VERSION" ]]; then
    return 1
fi

# Compare using bash arithmetic (avoid bc dependency)
REQUIRED_MAJOR=2
REQUIRED_MINOR=27
DETECTED_MAJOR=$(echo "$GLIBC_VERSION" | cut -d. -f1)
DETECTED_MINOR=$(echo "$GLIBC_VERSION" | cut -d. -f2)

if [[ $DETECTED_MAJOR -lt $REQUIRED_MAJOR ]]; then
    return 1
elif [[ $DETECTED_MAJOR -eq $REQUIRED_MAJOR && $DETECTED_MINOR -lt $REQUIRED_MINOR ]]; then
    return 1
fi

# Additional checks can be added here:
# - OS type (Linux, BSD, etc.)
# - Architecture (x86_64, aarch64, etc.)
# - Specific library availability

return 0
