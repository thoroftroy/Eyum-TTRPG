#!/bin/bash
# Eyum TTRPG Handbook Builder
# Combines all .md, .txt, .json files into a single handbook file.
# Usage: ./scripts/build-handbook.sh [output_file]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="${1:-"$PWD/Eyum-TTRPG-Handbook.txt"}"

IGNORE_DIRS=".git|.github|.obsidian|.trash|node_modules|__pycache__|.pyc"

echo "Building Eyum TTRPG Handbook..."
echo "Source: $ROOT"
echo "Output: $OUTPUT"
echo ""

# Clear output file
>"$OUTPUT"

{
  echo "========================================================================"
  echo "                     EYUM TTRPG - COMPLETE HANDBOOK"
  echo "========================================================================"
  echo "Generated: $(date)"
  echo "Source: Eyum TTRPG rulebook & assets"
  echo ""
  echo ""
} >>"$OUTPUT"

# Walk all .md, .txt, .json files, sorted by path
find "$ROOT" -type f \( -iname '*.md' -o -iname '*.txt' -o -iname '*.json' \) \
  ! -path '*/.git/*' \
  ! -path '*/.github/*' \
  ! -path '*/.obsidian/*' \
  ! -path '*/.trash/*' \
  ! -path '*/node_modules/*' \
  ! -path '*/__pycache__/*' \
  ! -path '*/output/*' \
  | sed "s|^$ROOT/||" \
  | sort \
  | while IFS= read -r relpath; do

  fullpath="$ROOT/$relpath"

  # Skip .pyc and __pycache__
  if echo "$relpath" | grep -qiE '(\.pyc$|__pycache__)'; then
    continue
  fi

  # Determine file type label
  case "${relpath,,}" in
    *.md)   label="MARKDOWN" ;;
    *.txt)  label="TEXT" ;;
    *.json) label="JSON DATA" ;;
    *)      label="FILE" ;;
  esac

  {
    echo ""
    echo "========================================================================"
    echo "  $label: $relpath"
    echo "========================================================================"
    echo ""
    cat "$fullpath"
    echo ""
    echo ""
  } >>"$OUTPUT"

  echo "  Added: $relpath"
done

# Count stats
total_lines=$(wc -l <"$OUTPUT")
total_files=$(find "$ROOT" -type f \( -iname '*.md' -o -iname '*.txt' -o -iname '*.json' \) \
  ! -path '*/.git/*' ! -path '*/.github/*' ! -path '*/.obsidian/*' \
  ! -path '*/.trash/*' ! -path '*/node_modules/*' ! -path '*/__pycache__/*' \
  ! -path '*/output/*' | wc -l)

echo ""
echo "=========================================="
echo "Handbook complete!"
echo "  Files included: $total_files"
echo "  Total lines:    $total_lines"
echo "  Output:         $OUTPUT"
echo "=========================================="
