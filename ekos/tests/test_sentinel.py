#!/usr/bin/env python3
"""Unit test: ekos_sentinel.evaluate_cycle decision logic - roof-first, safety_hold
set/clear by the safety verdict, debounce ONLY when the roof is OPEN, unknown-roof
staleness, defer-to-Ekos-close, INDI-down, ensure-connected. All INDI/dbus/Mattermost
is mocked, so this runs anywhere. Run: python3 test_sentinel.py"""
import os, sys, types, logging, time
EKOS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.modules["dbus"] = types.ModuleType("dbus")          # stub so import works w/o dbus
_ekos_cli = types.ModuleType("ekos_cli")
class _StubDbus: pass
_ekos_cli.EkosDbus = _StubDbus
sys.modules["ekos_cli"] = _ekos_cli
sys.path.insert(0, EKOS)
import observatorylib as obs
import ekos_sentinel as S
logging.basicConfig(level=logging.CRITICAL)
cfg = obs.ObservatoryConfig(os.path.join(EKOS, "ekos_sentinel_config_production.yaml"))

PASS = [0]; FAIL = [0]
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name); (PASS if cond else FAIL)[0] += 1

class FakeO:
    def __init__(self, weather="Ok", roof=True, parked=True, park_ok=True, close_ok=True, cooler_on=False):
        self.weather = weather; self._roof = roof; self._parked = parked
        self.park_ok = park_ok; self.close_ok = close_ok; self.calls = []; self.max_retries = 5
        self._cooler_on = cooler_on
    def ensure_devices_connected(self): self.calls.append(("ensure",)); return True
    def indi_get(self, prop): return self.weather
    def is_roof_closed(self): return self._roof          # True / False / None
    def is_parked(self): return self._parked
    def park_mount(self): self.calls.append(("park_mount",)); return self.park_ok
    def close_cap(self): self.calls.append(("close_cap",)); return True
    def close_roof(self): self.calls.append(("close_roof",)); return self.close_ok
    def set_camera_setpoint(self, t, s): self.calls.append(("set_camera_setpoint", t, s)); return True
    def cooler_is_on(self): return self._cooler_on       # True / False / None
    def cooler_off(self): self.calls.append(("cooler_off",)); self._cooler_on = False; return True
    def state_snapshot(self): return {"mount_parked": self._parked, "roof_closed": self._roof}
    def report(self, sev, title, body=None, state=None): self.calls.append(("report", sev, title))
    def names(self): return [c[0] for c in self.calls]

class FakeDbus:
    def stop_scheduler(self): pass
    def abort_all_operations(self): return True
class FakeLease:
    def __init__(self, role): self.role = role
    def acquire(self, force=False): return True
    def release(self): pass

HOLD = {"set": False}
obs.set_safety_hold = lambda r: HOLD.__setitem__("set", True)
obs.clear_safety_hold = lambda: HOLD.__setitem__("set", False)
obs.is_safety_hold = lambda: HOLD["set"]
obs.Lease = FakeLease
_LEASE = {"val": None, "fresh": False}
obs.read_lease = lambda *a, **k: _LEASE["val"]
obs.lease_is_fresh = lambda lease, ttl=90: _LEASE["fresh"]

def st0(**kw):
    s = {"unsafe_count": 0, "hold_set": False, "indi_down": False,
         "roof_unknown_since": None, "cooler_on_since": None}
    s.update(kw); return s
def reset(): HOLD["set"] = False; _LEASE["val"] = None; _LEASE["fresh"] = False

# 1. ensure_devices_connected called each cycle
reset(); o = FakeO(); S.evaluate_cycle(o, FakeDbus(), cfg, st0())
check("ensure_devices_connected called each cycle", "ensure" in o.names())

# 2. roof CLOSED + unsafe -> hold set IMMEDIATELY, no debounce, no failsafe
reset(); o = FakeO(weather="Alert", roof=True); st = st0()
S.evaluate_cycle(o, FakeDbus(), cfg, st)
check("closed+unsafe: hold set immediately", HOLD["set"] is True)
check("closed+unsafe: no failsafe, no debounce", "park_mount" not in o.names() and st["unsafe_count"] == 0)

# 3. roof CLOSED + safe -> NO hold (cleared), opening allowed
reset(); HOLD["set"] = True; o = FakeO(weather="Ok", roof=True)
S.evaluate_cycle(o, FakeDbus(), cfg, st0(hold_set=True))
check("closed+safe: hold cleared (opening allowed)", HOLD["set"] is False)

# 4. roof OPEN + unsafe -> hold set; debounce until max(3) then failsafe
reset(); o = FakeO(weather="Alert", roof=False, parked=False); st = st0()
S.evaluate_cycle(o, FakeDbus(), cfg, st)
check("open+unsafe: hold set on first cycle", HOLD["set"] is True)
S.evaluate_cycle(o, FakeDbus(), cfg, st)
check("open+unsafe: still debouncing (no failsafe yet)", "park_mount" not in o.names())
S.evaluate_cycle(o, FakeDbus(), cfg, st)
check("open+unsafe: failsafe on 3rd (park+close)", "park_mount" in o.names() and "close_roof" in o.names())

# 5. roof OPEN + safe -> hold cleared, no action
reset(); HOLD["set"] = True; o = FakeO(weather="Ok", roof=False)
S.evaluate_cycle(o, FakeDbus(), cfg, st0(hold_set=True))
check("open+safe: hold cleared, no action", HOLD["set"] is False and "park_mount" not in o.names())

# 6. roof UNKNOWN + unsafe -> hold set; wait under timeout, act over timeout
reset(); o = FakeO(weather="Alert", roof=None, parked=True); st = st0()
S.evaluate_cycle(o, FakeDbus(), cfg, st)
check("unknown+unsafe: hold set", HOLD["set"] is True)
check("unknown+unsafe: NO failsafe under timeout", "park_mount" not in o.names() and st["roof_unknown_since"])
st["roof_unknown_since"] = time.time() - 200
o2 = FakeO(weather="Alert", roof=None, parked=True)
S.evaluate_cycle(o2, FakeDbus(), cfg, st)
check("unknown+unsafe > timeout: failsafe (assume open)", "park_mount" in o2.names())

# 7. defer to a fresh 'close' lease (Ekos shutting down)
reset(); _LEASE["val"] = {"role": "close"}; _LEASE["fresh"] = True
o = FakeO(weather="Alert", roof=False, parked=False)
S.evaluate_cycle(o, FakeDbus(), cfg, st0(unsafe_count=2))
check("defer: no failsafe while Ekos close lease fresh", "park_mount" not in o.names())

# 8. INDI down -> no action
reset(); o = FakeO(weather=None, roof=None); st = st0()
S.evaluate_cycle(o, FakeDbus(), cfg, st)
check("indi-down: marked down + no action", st["indi_down"] is True and "park_mount" not in o.names())

# 9. fan guard: roof closed + cooler on -> arm timer, no cooler_off yet
reset(); o = FakeO(weather="Ok", roof=True, cooler_on=True); st = st0()
S.evaluate_cycle(o, FakeDbus(), cfg, st)
check("fan guard: cooler on -> armed, no cooler_off yet", "cooler_off" not in o.names() and st["cooler_on_since"])

# 10. fan guard: warm-up timeout elapsed -> cooler_off
st["cooler_on_since"] = time.time() - (cfg.get("sequence.warm_timeout", 600) + 100)
o2 = FakeO(weather="Ok", roof=True, cooler_on=True)
S.evaluate_cycle(o2, FakeDbus(), cfg, st)
check("fan guard: timeout elapsed -> cooler_off", "cooler_off" in o2.names() and st["cooler_on_since"] is None)

# 11. fan guard: roof OPEN resets the timer, never disables the cooler (may be imaging)
reset(); o = FakeO(weather="Ok", roof=False, cooler_on=True)
st = st0(cooler_on_since=time.time() - 9999)
S.evaluate_cycle(o, FakeDbus(), cfg, st)
check("fan guard: roof open resets timer, no cooler_off",
      "cooler_off" not in o.names() and st["cooler_on_since"] is None)

print("\n{} passed, {} failed".format(PASS[0], FAIL[0]))
sys.exit(1 if FAIL[0] else 0)
