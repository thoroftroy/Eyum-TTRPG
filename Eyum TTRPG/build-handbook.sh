#!/bin/bash
# Eyum TTRPG Handbook Builder
# Combines all .md, .txt, .json files into a single handbook file.
# Usage: ./scripts/build-handbook.sh [output_file]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="${1:-"$PWD/Eyum-TTRPG-Handbook.txt"}"
EXCLUDE_DIRS=".git|.github|.obsidian|.trash|node_modules|__pycache__|.pyc"

echo "=========================================="
echo "  Eyum TTRPG Handbook Builder"
echo "=========================================="
echo ""
echo "Source directory: $ROOT"
echo "Output file:      $OUTPUT"
echo ""

# Check if output file already exists
if [ -f "$OUTPUT" ]; then
  echo "WARNING: Output file already exists!"
  echo "  -> Existing file will be OVERWRITTEN"
  echo "  -> File size: $(du -h "$OUTPUT" | cut -f1)"
  echo ""
fi

# Clear output file
echo "Creating output file..."
>"$OUTPUT"
echo "  -> Output file ready for writing"
echo ""

{
  echo "========================================================================"
  echo "                     EYUM TTRPG - COMPLETE HANDBOOK"
  echo "========================================================================"
  echo "Generated: $(date)"
  echo "Source: Eyum TTRPG rulebook & assets"
  echo ""
  echo ""
} >>"$OUTPUT"

echo "Collecting files..."
echo "  Excluded directories: .git, .github, .obsidian, .trash,"
echo "                        node_modules, __pycache__, output,"
echo "                        Character Manager/"
echo ""

# Walk all .md, .txt, .json files, sorted by path
find "$ROOT" -type f \( -iname '*.md' -o -iname '*.txt' -o -iname '*.json' \) \
  ! -path '*/.git/*' \
  ! -path '*/.github/*' \
  ! -path '*/.obsidian/*' \
  ! -path '*/.trash/*' \
  ! -path '*/node_modules/*' \
  ! -path '*/__pycache__/*' \
  ! -path '*/output/*' \
  ! -path '*/Character Manager/*' \
  ! -name 'Eyum-TTRPG-Handbook.txt' \
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
total_included=$(find "$ROOT" -type f \( -iname '*.md' -o -iname '*.txt' -o -iname '*.json' \) \
  ! -path '*/.git/*' ! -path '*/.github/*' ! -path '*/.obsidian/*' \
  ! -path '*/.trash/*' ! -path '*/node_modules/*' ! -path '*/__pycache__/*' \
  ! -path '*/output/*' ! -path '*/Character Manager/*' \
  ! -name 'Eyum-TTRPG-Handbook.txt' | wc -l)

total_excluded=$(find "$ROOT" -type f \( -iname '*.md' -o -iname '*.txt' -o -iname '*.json' \) \
  -path '*/Character Manager/*' 2>/dev/null | wc -l)

echo ""
echo "=========================================="
echo "  Handbook build complete!"
echo "=========================================="
echo ""
echo "  Files included:      $total_included"
echo "  Files excluded (CM): $total_excluded"
echo "  Total lines written: $total_lines"
echo "  Output file:         $OUTPUT"
echo ""

if [ "$total_excluded" -gt 0 ]; then
  echo "  Note: $total_excluded file(s) from 'Character Manager/'"
  echo "        were excluded from the handbook."
fi
echo ""
echo "  Done."
