#!/usr/bin/env bash
# CometTrain demo - exercises every surface end to end, unattended.
# Nothing is prompted for, nothing is installed and nothing is written to disk.
# Usage: bash demo.sh
set -uo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
status=0

section() {
  printf '\n$ %s\n' "$*"
}

demo() {
  # demo <expected-exit-code> <comettrain arguments...>
  local expected="$1"
  shift
  section "$PYTHON comettrain.py $*"
  "$PYTHON" comettrain.py "$@"
  local code=$?
  printf '[exit %s]\n' "$code"
  if [ "$code" -ne "$expected" ]; then
    printf 'demo: expected exit %s but got %s\n' "$expected" "$code" >&2
    status=1
  fi
}

printf 'CometTrain demo - offline comet lookup, standard library only\n'

demo 0 list
demo 0 show encke
demo 0 show "halley's comet"
demo 0 show tempel
demo 0 show bernardinelli
demo 1 show zzz
demo 0 perihelion --date 2023-10-20 --window 30
demo 0 perihelion --date 2024-06-30 --window 1
demo 0 calendar --from 2026-01-01 --days 1095
demo 0 calendar --from 9999-12-01 --days 365
demo 2 perihelion --date 2023-02-30 --window 30
demo 2 frobnicate
demo 0 --help

printf '\n'
if [ "$status" -eq 0 ]; then
  echo "demo: every surface behaved as documented."
else
  echo "demo: at least one surface returned an unexpected exit code." >&2
fi
exit "$status"
