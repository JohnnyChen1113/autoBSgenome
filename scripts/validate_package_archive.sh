#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: validate_package_archive.sh ARCHIVE PACKAGE" >&2
  exit 2
fi

archive=$1
package=$2
if [ ! -f "$archive" ]; then
  echo "ERROR: archive does not exist: $archive" >&2
  exit 1
fi

validation_tmp=$(mktemp -d "${TMPDIR:-/tmp}/autobsgenome-archive.XXXXXX")
cleanup() {
  rm -rf -- "$validation_tmp"
}
trap cleanup EXIT

hash_input="$validation_tmp/hash-input"
hash_output="$validation_tmp/hash.txt"
contents="$validation_tmp/contents.txt"
mkfifo "$hash_input"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum < "$hash_input" > "$hash_output" &
else
  shasum -a 256 < "$hash_input" > "$hash_output" &
fi
hash_pid=$!

set +e
tee "$hash_input" < "$archive" | tar -tzf - > "$contents"
pipeline_status=$?
wait "$hash_pid"
hash_status=$?
set -e

if [ "$pipeline_status" -ne 0 ] || [ "$hash_status" -ne 0 ]; then
  echo "ERROR: archive stream validation failed" >&2
  exit 1
fi

grep -Fxq "${package}/DESCRIPTION" "$contents"
grep -Fxq "${package}/inst/extdata/single_sequences.2bit" "$contents"
awk 'NR == 1 { print $1 }' "$hash_output"
