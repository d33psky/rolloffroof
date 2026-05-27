#!/bin/bash
# Run the observatory unit tests. No INDI / dbus / Mattermost needed (all mocked),
# so this is safe to run anywhere, including CI.
set -e
cd "$(dirname "$0")"
python3 test_reporter.py
echo
python3 test_sentinel.py
echo
echo "all unit tests passed"
