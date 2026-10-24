#!/bin/sh
# Root-owned forced command for the dedicated, unprivileged SSH refresh account.
set -eu
export PATH=/usr/bin:/bin
export PYTHONPATH=/opt/13f-intelligence/src
export PYTHONUTF8=1
cd /opt/13f-intelligence
case "${SSH_ORIGINAL_COMMAND:-}" in
  inspect)
    exec /opt/13f-intelligence/.venv/bin/python scripts/refresh_schedule.py
    ;;
  refresh)
    set -a
    . /etc/thirteenf/refresh.env
    set +a
    exec /opt/13f-intelligence/.venv/bin/python scripts/refresh_schedule.py --execute
    ;;
  *)
    echo 'DENIED: only inspect or refresh is permitted' >&2
    exit 64
    ;;
esac
