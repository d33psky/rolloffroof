#!/usr/bin/env python3
"""Unit test for observatorylib tri-state device-connection logic and the
lease-aware ensure_devices_connected. No INDI/dbus/MM needed - indi_get/set
are stubbed and lease helpers monkey-patched. Run: python3 test_observatorylib.py"""
import os, sys
EKOS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EKOS)
import observatorylib as obs

PASS=[0]; FAIL=[0]
def check(n,c): print(("PASS " if c else "FAIL ")+n); (PASS if c else FAIL)[0]+=1

cfg = obs.ObservatoryConfig(os.path.join(EKOS, "ekos_sentinel_config_production.yaml"))
o = obs.Observatory("localhost", cfg, name="test")

# In-memory INDI state; indi_set mutates it (simulating driver actuation).
_indi = {}
_set_calls = []
def _set(prop, val):
    _set_calls.append((prop, val)); _indi[prop] = val; return True
o.indi_get = lambda p: _indi.get(p)
o.indi_set = _set
# Immediate-eval _wait_until (no real polling).
o._wait_until = lambda pred, timeout: pred()
# Lease state monkey-patched at module level (read_lease + lease_is_fresh).
_lease = {"val": None, "fresh": False}
obs.read_lease     = lambda *a, **k: _lease["val"]
obs.lease_is_fresh = lambda lease, ttl=90: _lease["fresh"]

DEV = "Dome Scripting Gateway"
CONN = "{}.CONNECTION.CONNECT".format(DEV)
def reset():
    _indi.clear(); _set_calls.clear()
    _lease["val"] = None; _lease["fresh"] = False
    o.safety_devices = lambda: [DEV]

# ---- is_device_connected: tri-state ----
reset(); _indi[CONN] = "On"
check("is_device_connected True when CONNECT=On", o.is_device_connected(DEV) is True)
reset(); _indi[CONN] = "Off"
check("is_device_connected False when CONNECT=Off", o.is_device_connected(DEV) is False)
reset()   # no CONNECT entry -> indi_get returns None
check("is_device_connected None when value unreadable", o.is_device_connected(DEV) is None)
check("is_device_connected None when device falsy/empty", o.is_device_connected("") is None)

# ---- connect_device behaviour ----
reset(); _indi[CONN] = "On"
check("connect_device True idempotent no-op", o.connect_device(DEV) is True and not _set_calls)

reset()   # state None
check("connect_device refuses-with-False on None (no poking)",
      o.connect_device(DEV) is False and not _set_calls)

reset(); _indi[CONN] = "Off"
check("connect_device False -> sends CONNECT=On + verifies",
      o.connect_device(DEV) is True and (CONN, "On") in _set_calls)

# ---- ensure_devices_connected: lease awareness ----
reset(); _lease["val"] = {"role": "open"}; _lease["fresh"] = True; _indi[CONN] = "Off"
check("ensure: open lease fresh -> defers (no reconnect attempted)",
      o.ensure_devices_connected() is True and not _set_calls)

reset(); _lease["val"] = {"role": "close"}; _lease["fresh"] = True; _indi[CONN] = "Off"
check("ensure: close lease fresh -> defers", o.ensure_devices_connected() is True and not _set_calls)

# A stale lease (fresh=False) must NOT block reconnects.
reset(); _lease["val"] = {"role": "open"}; _lease["fresh"] = False; _indi[CONN] = "Off"
check("ensure: stale lease -> does NOT defer (reconnect proceeds)",
      o.ensure_devices_connected() is True and (CONN, "On") in _set_calls)

# A lease with a different role (e.g. our own no-name) does NOT defer either.
reset(); _lease["val"] = {"role": "other"}; _lease["fresh"] = True; _indi[CONN] = "Off"
check("ensure: non-open/close lease role -> does NOT defer",
      o.ensure_devices_connected() is True and (CONN, "On") in _set_calls)

# ---- ensure_devices_connected: per-device tri-state ----
reset(); _indi[CONN] = "On"
check("ensure: state True -> no reconnect", o.ensure_devices_connected() is True and not _set_calls)

reset()   # state None
check("ensure: state None -> silent skip (no reconnect, returns True)",
      o.ensure_devices_connected() is True and not _set_calls)

reset(); _indi[CONN] = "Off"
check("ensure: state False -> reconnects (CONNECT=On sent)",
      o.ensure_devices_connected() is True and (CONN, "On") in _set_calls)

print("\n{} passed, {} failed".format(PASS[0], FAIL[0]))
sys.exit(1 if FAIL[0] else 0)
