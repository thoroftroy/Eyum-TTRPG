#!/usr/bin/env bash

set -e

OUTPUT="project_last_2_days.txt"

echo "Writing to $OUTPUT..."

{
    echo "=================================================="
    echo "COMMITS FROM THE LAST 2 DAYS"
    echo "=================================================="
    echo

    git log --since="2 days ago" --reverse --full-history --stat

    echo
    echo "=================================================="
    echo "DIFFS FROM THE LAST 2 DAYS"
    echo "=================================================="
    echo

    git log --since="2 days ago" --reverse --full-history -p

} > "$OUTPUT"

echo
echo "Done!"
echo "Created: $OUTPUT"
