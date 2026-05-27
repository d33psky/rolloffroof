#!/bin/bash
# Static checks (pyflakes, if installed) + unit tests for the observatory code.
# No INDI / dbus / Mattermost needed (all mocked) - safe anywhere, including CI.
# Install the linter with:  sudo apt install python3-pyflakes
set -e
cd "$(dirname "$0")"
EKOS="$(cd .. && pwd)"

if python3 -c "import pyflakes" 2>/dev/null; then
    echo "== pyflakes =="
    python3 -m pyflakes \
        "$EKOS/observatorylib.py" "$EKOS/ekos_sentinel.py" "$EKOS/ekos_cli.py" \
        "$EKOS/observatory-open" "$EKOS/observatory-close" \
        test_reporter.py test_sentinel.py
    echo "pyflakes clean"
else
    echo "(pyflakes not installed - skipping static checks; sudo apt install python3-pyflakes)"
fi

echo "== unit tests =="
python3 test_reporter.py
echo
python3 test_sentinel.py
echo
echo "all checks passed"
