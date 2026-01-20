#!/bin/bash

DEPLOY_DIR="/deploy/$PLATFORM"
LIB_DIR="$DEPLOY_DIR/lib"

echo "=========================================="
echo "Collecting shared library dependencies..."
echo "Platform: $PLATFORM"
echo "=========================================="

# Create lib directory
mkdir -p "$LIB_DIR"

# Track if we copied any files in this iteration
copied_count=0

# Loop until no new dependencies are found
iteration=1
while true; do
    echo ""
    echo "Iteration $iteration: Scanning for dependencies..."

    # Find all ELF files (executables and shared objects) in the deploy directory
    elf_files=$(find "$DEPLOY_DIR" -type f -executable -o -type f -name "*.so*" | while read -r file; do
        if file "$file" | grep -q "ELF"; then
            echo "$file"
        fi
    done)

    # Track copies made in this iteration
    iteration_copies=0

    # For each ELF file, get its dependencies
    while IFS= read -r elf_file; do
        # Run ldd and extract dependency paths
        dep_paths=$(ldd "$elf_file" 2>/dev/null | grep "=>" | awk '{print $3}')

        while IFS= read -r dep_path; do
            # Skip empty lines and special entries
            if [[ -z "$dep_path" ]]; then
                continue
            fi

            # Check if the dependency exists and is a real file
            if [[ ! -f "$dep_path" ]]; then
                continue
            fi

            # Get the basename of the dependency
            dep_name=$(basename "$dep_path")
            dest_path="$LIB_DIR/$dep_name"

            # Copy if it doesn't already exist
            if [[ ! -f "$dest_path" ]]; then
                echo "  Copying: $dep_path -> $dest_path"
                cp "$dep_path" "$dest_path"
                ((iteration_copies++))
            fi
        done <<< "$dep_paths"
    done <<< "$elf_files"

    echo "Copied $iteration_copies files in iteration $iteration"

    # If no files were copied, we're done
    if [[ $iteration_copies -eq 0 ]]; then
        echo ""
        echo "No new dependencies found. Collection complete!"
        break
    fi

    ((copied_count += iteration_copies))
    ((iteration++))
done

echo ""
echo "=========================================="
echo "Dependency collection complete!"
echo "Total files copied: $copied_count"
echo "=========================================="
