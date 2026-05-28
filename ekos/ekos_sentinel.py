#!/usr/bin/env python3

DESCRIPTION = """
EKOS Sentinel, version 2.1 - always-on observatory safety failsafe.

Originally created because the EKOS scheduler (KStars 3.2.0) would open the
observatory on good weather but not close it when weather turned bad. Newer
KStars handles weather again, so the sentinel's job is now to VERIFY that Ekos
actually does its job and to act as an independent failsafe if it does not -
regardless of KStars version and guarding against future regressions.

All hardware control is shared with the Ekos scheduler sequence scripts
(observatory-open / observatory-close) through observatorylib, so there is a
single, tested source of truth for park / close / warm / verify. The sentinel
talks directly to the standalone INDI server (and, when configured, the
10Micron LX200 API), so it keeps working even after Ekos has stopped.

Main loop (once per safety.main_loop_sleep_seconds):
    INDI reachable?
      no  -> report once, keep looping (never act on hardware we can't see)
      yes -> weather safe?
               yes -> clear the safety hold; idle (roof open = imaging, closed = ok)
               no  -> set the safety hold (do-not-open); then by ROOF state:
                        closed  -> safe, nothing to do (no debounce)
                        unknown -> wait; after roof_unknown_timeout assume OPEN
                        open    -> debounce (safety.unsafe_count_max), then, if
                                   Ekos is not already closing (no fresh "close"
                                   lease) -> FAILSAFE: stop scheduler + abort ekos,
                                   force-take the lease, gentle-warm the camera,
                                   park mount, close cap, close roof.

Coordination with the sequence scripts (observatorylib):
    * Lease     - the scripts hold "open"/"close" while driving hardware. The
                  sentinel DEFERS to a fresh "close" lease (Ekos is shutting
                  down - let it), and force-preempts otherwise.
    * Safety hold - sentinel-owned 'do not open' flag; set whenever the safety
                  proxy says unsafe so an in-progress open aborts (close beats
                  open), cleared when it is safe again.

Configuration: YAML (see ekos_sentinel_config_production.yaml /
ekos_sentinel_config_simulator.yaml). Pass --config or rely on the production
default next to this script.
"""

import argparse
import logging
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import observatorylib as obs
from ekos_cli import EkosDbus

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "ekos_sentinel_config_production.yaml")

logger = logging.getLogger("ekos_sentinel")


# --------------------------------------------------------------------------
# Helpers (module level so they are unit-testable)
# --------------------------------------------------------------------------
def safe_snapshot(o):
    """state_snapshot for a diagnostic report; never let it crash the failsafe
    (it touches the LX200 socket, which can fail)."""
    try:
        return o.state_snapshot()
    except Exception as e:  # pragma: no cover - defensive
        logger.error("state_snapshot failed: %s", e)
        return None


def alert(o, reason):
    """Was alert_and_abort(): report critical to Mattermost + log, but do NOT
    sys.exit. A failsafe daemon must stay alive and retry on the next cycle, so
    'abort' now means 'abort this emergency attempt', not 'kill the sentinel'."""
    logger.critical("ALERT: %s", reason)
    o.report("critical", "ALERT (failsafe could not complete): " + reason, state=safe_snapshot(o))


def read_weather(o, config):
    """Return (reachable, safe).

    reachable=False means INDI did not answer - the loop must NOT act on
    hardware it cannot see. This is re-implemented here (rather than calling
    o.is_weather_safe()) precisely so we can tell 'unreadable' (None) apart from
    'unsafe': the lib's is_weather_safe() collapses both to False."""
    prop = config.get("indi.weather.property")
    ok = config.get("indi.weather.ok_setting")
    stations = config.get("indi.weather.station_indexes", [1])
    if not prop:
        return True, True
    n_ok = 0
    for st in stations:
        val = o.indi_get("{}_{}".format(prop, st))
        if val is None:
            return False, False
        if val == ok:
            n_ok += 1
    return True, n_ok == len(stations)


def scheduler_is_closing():
    """True if a fresh 'close' lease is held - i.e. the Ekos scheduler is
    running its shutdown sequence. The sentinel defers to that (let Ekos do its
    job); the close scripts' POST always runs cooler-off, so it is safe to wait."""
    lease = obs.read_lease()
    return obs.lease_is_fresh(lease) and (lease or {}).get("role") == "close"


def _safe_dbus(label, fn):
    """Call an EkosDbus method, swallowing failures INCLUDING SystemExit.
    ekos_cli's setup_*_iface() calls sys.exit(1) on DBusException when KStars is
    down; SystemExit is not an Exception, so without this the failsafe would die
    exactly when Ekos is absent - the case it exists to handle."""
    try:
        return fn()
    except SystemExit as e:
        logger.warning("%s: KStars/dbus unavailable (exit %s) - continuing", label, e.code)
    except Exception as e:
        logger.warning("%s failed: %s", label, e)
    return None


def failsafe_close(o, ekos_dbus, config, reason):
    """Emergency shutdown: weather confirmed unsafe, roof open, Ekos not closing.

    Order: stop Ekos -> force-take the lease -> gentle-warm (fire-and-forget) ->
    park mount -> close cap -> close roof. The camera is warmed with a setpoint
    RAMP, not an immediate cooler_off: the TEC idles toward 0%% on its own and a
    gentle ramp avoids thermal shock, with no follow-up cut needed in an
    emergency (DECISION 2). The scheduled close still does the full
    warm-then-cooler_off in its POST phase."""
    logger.warning("FAILSAFE close: %s", reason)
    o.report("warn", "FAILSAFE: weather unsafe, roof open, Ekos not closing", body=reason, state=safe_snapshot(o))

    _safe_dbus("stop_scheduler", ekos_dbus.stop_scheduler)
    _safe_dbus("abort_all_operations", ekos_dbus.abort_all_operations)

    # Force-preempt any holder: we already set the safety hold, so an
    # in-progress open will abort; force guarantees we can act without waiting.
    lease = obs.Lease("sentinel")
    lease.acquire(force=True)
    try:
        # Start the warm ramp now so it overlaps park + close (non-blocking).
        o.set_camera_setpoint(config.get("sequence.warm_target", 40),
                              config.get("sequence.warm_slope", 5))
        if not o.park_mount():
            alert(o, "mount failed to park after retries; NOT closing roof")
            return
        o.close_cap()
        if not o.close_roof():
            alert(o, "mount parked but roof failed to close")
            return
        o.report("warn", "FAILSAFE complete: mount parked, roof closed, camera warming", state=safe_snapshot(o))
    finally:
        lease.release()


def narrate_shutdown(o, st):
    """Report (once each) that we observed Ekos shutting down and that we observed
    the completed end-state. Both flags reset when the shutdown-complete marker is
    cleared (by observatory-open at the start of the next session) so each shutdown
    gets its own pair of reports.

    'Observing' fires on first sight of a fresh 'close' lease in the current
    shutdown window. 'Observed' fires once after the marker is set AND the end
    state is verified parked + roof-closed (a bad state stays silent so the
    failsafe path owns alerting). All info severity (no @hans mention)."""
    prev = st.get("shutdown_complete_prev", False)
    curr = obs.is_shutdown_complete()
    if prev and not curr:                         # leading edge: marker cleared -> new session
        st["shutdown_observing_reported"] = False
        st["shutdown_observed_reported"] = False
    st["shutdown_complete_prev"] = curr

    if curr:
        if not st.get("shutdown_observed_reported"):
            state = o.state_snapshot()
            if state.get("mount_parked") and state.get("roof_closed") is True:
                o.report("info", "Ekos shutdown observed: state OK, no intervention needed",
                         state=state)
                st["shutdown_observed_reported"] = True
        return

    lease = obs.read_lease()
    if lease and lease.get("role") == "close" and obs.lease_is_fresh(lease):
        if not st.get("shutdown_observing_reported"):
            o.report("info",
                     "Observing Ekos shutdown by observatory-close, deferring while it completes")
            st["shutdown_observing_reported"] = True


def guard_camera_fan(o, config, st):
    """Keep the camera fan off while the observatory is idle. The fan tracks the
    cooler ENABLE switch (CCD_COOLER.COOLER_ON), which the INDI temperature-ramp loop
    re-enables; observatory-close normally disables it after the warm-up, but a
    crash / restart / Ekos reconnect can leave it running. Called ONLY when the roof
    is closed (imaging is impossible, so the cooler is never legitimately needed).

    Worst-case timer: from when we first see the cooler on, wait sequence.warm_timeout
    (the max warm-up duration) before forcing it off, so a genuine gentle warm-up in
    progress is never cut short. Restart-safe by design - a fresh guard re-waits the
    full timeout, so it can never truncate a real warm-up."""
    on = o.cooler_is_on()
    if on is not True:                      # off, or unreadable -> nothing to guard
        st["cooler_on_since"] = None
        return
    now = time.time()
    timeout = config.get("sequence.warm_timeout", 600)
    if st.get("cooler_on_since") is None:
        st["cooler_on_since"] = now
        logger.info("camera cooler/fan on while roof closed - will disable after %ss (warm-up guard)",
                    timeout)
        return
    elapsed = now - st["cooler_on_since"]
    if elapsed >= timeout:
        if o.cooler_off():
            logger.info("camera cooler/fan disabled (idle, warm-up guard elapsed)")
            st["cooler_on_since"] = None
        else:
            logger.warning("failed to disable camera cooler/fan - will retry next cycle")
    else:
        logger.debug("camera cooler/fan on (%.0f/%ss warm-up guard)", elapsed, timeout)


def evaluate_cycle(o, ekos_dbus, config, st):
    """One decision cycle. `st` carries loop state {unsafe_count, hold_set,
    indi_down, roof_unknown_since, cooler_on_since, shutdown_complete_prev,
    shutdown_observing_reported, shutdown_observed_reported}. Extracted so the
    logic is unit-testable.

    Check the ROOF first - a closed roof needs no close and no debounce. The
    safety-proxy verdict (weather + UPS + darkness) then decides the 'do not open'
    safety_hold. The debounce gates ONLY the disruptive close of an OPEN roof."""
    # Keep our own INDI devices connected - never depend on Ekos for connectivity.
    o.ensure_devices_connected()
    narrate_shutdown(o, st)               # info-level acks of shutdown start / end

    reachable, safe = read_weather(o, config)
    if not reachable:
        if not st["indi_down"]:
            o.report("warn", "INDI unreachable - sentinel cannot read observatory state")
            st["indi_down"] = True
        logger.error("INDI unreachable; cannot read safety state this cycle")
        return
    if st["indi_down"]:
        o.report("info", "INDI reachable again")
        st["indi_down"] = False

    def raise_hold(reason):
        if not st["hold_set"]:
            obs.set_safety_hold(reason)
            st["hold_set"] = True

    def drop_hold():
        if st["hold_set"] or obs.is_safety_hold():
            obs.clear_safety_hold()
            st["hold_set"] = False

    roof = o.is_roof_closed()   # True=closed / False=open / None=unknown

    # Roof closed = secured: never a close, never a debounce. The proxy verdict
    # only decides whether opening is blocked.
    if roof is True:
        st["unsafe_count"] = 0
        st["roof_unknown_since"] = None
        guard_camera_fan(o, config, st)   # idle: ensure the camera fan is not left on
        if safe:
            drop_hold()
            logger.info("safe, roof closed (opening allowed)")
        else:
            raise_hold("conditions unsafe (roof already closed)")
            logger.info("unsafe, roof closed - safe (opening blocked)")
        return

    # Roof open or unknown.
    st["cooler_on_since"] = None          # not idle -> reset the fan-guard timer
    if safe:
        st["unsafe_count"] = 0
        st["roof_unknown_since"] = None
        drop_hold()
        logger.info("safe, roof %s", "open" if roof is False else "unknown")
        return

    # Unsafe + roof open/unknown: block opening now, then work toward closing.
    raise_hold("conditions unsafe, roof not secured")

    if roof is None:
        # Absent reading is 'don't know', NOT open. A roof that stays unknown longer
        # than its max open/close time is itself a problem -> assume OPEN.
        now = time.time()
        st["roof_unknown_since"] = st["roof_unknown_since"] or now
        elapsed = now - st["roof_unknown_since"]
        timeout = config.get("safety.roof_unknown_timeout", 120)
        if elapsed < timeout:
            logger.warning("unsafe + roof state UNKNOWN (%.0f/%ss) - waiting, not acting yet",
                           elapsed, timeout)
            return
        logger.warning("unsafe + roof UNKNOWN for %.0fs (>%ss) - assuming OPEN and acting",
                       elapsed, timeout)
    else:
        # Roof positively open: debounce the disruptive close against weather blips.
        st["unsafe_count"] += 1
        unsafe_max = config.get("safety.unsafe_count_max", 3)
        if st["unsafe_count"] < unsafe_max:
            logger.info("unsafe + roof open (%d/%d) - debouncing before close",
                        st["unsafe_count"], unsafe_max)
            return

    st["roof_unknown_since"] = None
    if scheduler_is_closing():
        logger.warning("unsafe + roof open, but Ekos shutdown is in progress "
                       "(close lease held) - standing by")
    else:
        failsafe_close(o, ekos_dbus, config, "conditions unsafe, roof open, Ekos not closing")


# --------------------------------------------------------------------------
# CLI / main
# --------------------------------------------------------------------------
def _build_parser():
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        epilog='Only --indi_host is required for normal operation; the rest is for debugging and testing',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--indi_host', required=True, type=str, help='INDI server address')
    parser.add_argument('--config', type=str, help='configuration file path (YAML); defaults to the production config next to this script')
    parser.add_argument('--indi_command_retries', type=str, help='override safety.max_retries')
    parser.add_argument('--debug', action='store_true', help='enable debug level verbosity')
    parser.add_argument('--once', action='store_true', help='run the loop only once (debugging)')
    # test hooks (rewired onto Observatory)
    parser.add_argument('--get_weather_safety', action='store_true', help='test: print (reachable, safe)')
    parser.add_argument('--get_mount_safety', action='store_true', help='test: print is_parked()')
    parser.add_argument('--get_cap_safety', action='store_true', help='test: print is_cap_closed()')
    parser.add_argument('--get_roof_safety', action='store_true', help='test: print is_roof_closed()')
    parser.add_argument('--state', action='store_true', help='test: print a full state snapshot')
    parser.add_argument('--park_mount', action='store_true', help='test: park the mount')
    parser.add_argument('--unpark_mount', action='store_true', help='test: unpark the mount')
    parser.add_argument('--close_roof', action='store_true', help='test: close the roof')
    parser.add_argument('--open_roof', action='store_true', help='test: open the roof')
    parser.add_argument('--close_cap', action='store_true', help='test: close the cap')
    parser.add_argument('--warm_camera', action='store_true', help='test: gentle warm setpoint ramp')
    parser.add_argument('--cooler_off', action='store_true', help='test: switch the cooler off (verified)')
    return parser


def _run_test_hooks(args, o, config):
    """Handle the one-shot --<action> test flags. Returns True if one ran."""
    if args.get_weather_safety:
        logger.info("get_weather_safety (reachable, safe) = %s", read_weather(o, config)); return True
    if args.get_mount_safety:
        logger.info("is_parked = %s", o.is_parked()); return True
    if args.get_roof_safety:
        logger.info("is_roof_closed = %s", o.is_roof_closed()); return True
    if args.get_cap_safety:
        logger.info("is_cap_closed = %s", o.is_cap_closed()); return True
    if args.state:
        logger.info("state = %s", o.state_snapshot()); return True
    if args.park_mount:
        logger.info("park_mount = %s", o.park_mount()); return True
    if args.unpark_mount:
        logger.info("unpark_mount = %s", o.unpark_mount()); return True
    if args.close_roof:
        logger.info("close_roof = %s", o.close_roof()); return True
    if args.open_roof:
        logger.info("open_roof = %s", o.open_roof()); return True
    if args.close_cap:
        logger.info("close_cap = %s", o.close_cap()); return True
    if args.warm_camera:
        logger.info("warm_camera (setpoint ramp) = %s",
                    o.set_camera_setpoint(config.get("sequence.warm_target", 40),
                                          config.get("sequence.warm_slope", 5))); return True
    if args.cooler_off:
        logger.info("cooler_off = %s", o.cooler_off()); return True
    return False


def main():
    args = _build_parser().parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)-8s %(name)s %(message)s")

    config = obs.ObservatoryConfig(args.config or DEFAULT_CONFIG)
    o = obs.Observatory(args.indi_host, config, name="sentinel")
    if args.indi_command_retries:
        o.max_retries = int(args.indi_command_retries)
    ekos_dbus = EkosDbus()

    if _run_test_hooks(args, o, config):
        sys.exit(0)

    sleep_s = config.get("safety.main_loop_sleep_seconds", 60)
    # If the shutdown-complete marker is ALREADY set when we start, we did not
    # observe THIS shutdown happen - we inherited its aftermath. Pre-mark the
    # 'observed' flag so we don't fire a stale "shutdown observed" report for a
    # shutdown that may have happened hours ago. The marker is cleared by the
    # next observatory-open; the leading-edge reset in narrate_shutdown then
    # reopens narration for the next real cycle.
    inherited_marker = obs.is_shutdown_complete()
    st = {"unsafe_count": 0, "hold_set": False, "indi_down": False,
          "roof_unknown_since": None, "cooler_on_since": None,
          "shutdown_complete_prev": inherited_marker,
          "shutdown_observing_reported": False,
          "shutdown_observed_reported": inherited_marker}

    # One-shot test mode: no start/stop reports (those are for the long-running
    # screen instance), just run a single cycle.
    if args.once:
        evaluate_cycle(o, ekos_dbus, config, st)
        return

    # Long-running mode: report start now, and ensure a stop report fires on
    # exit - whether via Ctrl-C (SIGINT->KeyboardInterrupt) or SIGTERM. Map
    # SIGTERM to KeyboardInterrupt so both paths reach the 'finally' clause.
    def _sigterm_to_kbd(_signo, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _sigterm_to_kbd)
    pid = os.getpid()
    o.report("info", "Sentinel started (PID {})".format(pid))
    try:
        while True:
            try:
                evaluate_cycle(o, ekos_dbus, config, st)
            except Exception as e:
                logger.error("Unexpected error in main loop: %s. Will retry in %ss.", e, sleep_s)
            logger.debug("sleep %s", sleep_s)
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        pass
    finally:
        o.report("warn", "Sentinel stopped (PID {})".format(pid))


if __name__ == "__main__":
    main()
