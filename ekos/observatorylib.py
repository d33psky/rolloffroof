#!/usr/bin/env python3
"""
observatorylib - shared direct-INDI observatory control for the roll-off roof.

Single source of truth for the safety-critical hardware operations, used by
BOTH the Ekos scheduler sequence scripts (observatory-open / observatory-close)
AND ekos_sentinel.py. Everything talks directly to the standalone INDI server
(indi_getprop / indi_setprop) and, for the authoritative mount state, to the
10Micron's own LX200 API - so it keeps working even when Ekos has stopped.

Design rules (learned from incident 2026-05-26):
  * Operations are IDEMPOTENT and VERIFY-FIRST: if already in the wanted state,
    return success; otherwise act, then poll until verified.
  * Commands are RE-ISSUED on retry (not just re-polled) - a park that gets
    aborted mid-slew must be re-commanded, not waited on forever.
  * "Mount parked" is decided by the mount's own Gstat==5, NOT the INDI PARK
    switch (which flips to On instantly, while the mount is still slewing) and
    NOT a coordinate proximity hack. Gstat==5 is also exactly when the mount
    releases its lock, so it is the correct precondition for closing the roof
    (the dome "Mount Policy" interlock refuses while the mount is "locking").
  * A transiently-missing INDI field (e.g. DOME_PARK.STATE vanishing during a
    park) is treated as "in transition" - keep polling to timeout, never read
    a missing field as success.

Coordination (race guard) primitives also live here:
  * Lease  - heartbeat advisory mutex at /run/observatory/lease, steal-on-stale.
             Held only while an actor is actively driving hardware.
  * Emergency flag at /run/observatory/emergency - sentinel-owned; sequence
    scripts poll it between steps and abort so safety (close) beats open.

Reporting is folded in (state-aware Mattermost) and also exposed standalone:
  obs.report(...)              # instance, carries config + live state
  observatorylib.report(...)   # module-level one-shot for external callers
"""

import json
import logging
import os
import shlex
import socket
import subprocess
import threading
import time
from pathlib import Path

import requests
import yaml

logger = logging.getLogger("observatory")

# --------------------------------------------------------------------------
# Coordination paths / constants
# --------------------------------------------------------------------------
# Per-user tmpfs so both same-user actors (sentinel + sequence scripts) share
# it without root; falls back to /tmp if XDG_RUNTIME_DIR isn't set.
RUN_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "observatory")
LEASE_PATH = os.path.join(RUN_DIR, "lease")
EMERGENCY_PATH = os.path.join(RUN_DIR, "emergency")
DEFAULT_LEASE_TTL = 90  # seconds; lease older than this is considered stale


# --------------------------------------------------------------------------
# Configuration (dot-path access; shared by sentinel + scripts)
# --------------------------------------------------------------------------
class ObservatoryConfig:
    """YAML config with dot-path lookup, e.g. get('indi.mount.park_property')."""

    def __init__(self, config_file):
        if not config_file or not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        with open(config_file) as f:
            self.config = yaml.safe_load(f)

    def get(self, key_path, default=None):
        value = self.config
        for key in key_path.split('.'):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


# --------------------------------------------------------------------------
# Reporting (Mattermost; state-aware) - usable standalone
# --------------------------------------------------------------------------
SEVERITY_EMOJI = {"info": ":information_source:", "warn": ":warning:", "critical": ":rotating_light:"}


class Reporter:
    """Posts to Mattermost via the webhook URL in ~/.mattermosturl.

    Mirrors the long-standing obsy_shutdown_after.py mechanism so no new infra
    is needed on vostro. When vostro is folded into runme this collapses to a
    dispatch-alert call (email fallback + JSON audit log)."""

    def __init__(self, url_file=None, source="observatory"):
        self.url_file = url_file or os.path.join(str(Path.home()), ".mattermosturl")
        self.source = source
        self.logger = logging.getLogger("observatory.report")

    def report(self, severity, title, body=None, state=None):
        """severity in {info,warn,critical}. state is an optional dict of live
        readings (parked, roof, cooler_power, ...) appended to the message."""
        lines = [title]
        if body:
            lines.append(body)
        if state:
            lines.append("```\n" + "\n".join(f"{k}: {v}" for k, v in state.items()) + "\n```")
        text = "{} **[{}]** {}".format(SEVERITY_EMOJI.get(severity, ":warning:"),
                                       self.source, "\n".join(lines))
        self.logger.info("report[%s] %s", severity, title)
        try:
            with open(self.url_file) as f:
                url = f.read().rstrip("\n")
            r = requests.post(url, data={"payload": json.dumps({"text": text})}, timeout=10)
            if r.status_code != 200:
                self.logger.error("Mattermost POST HTTP %s: %s", r.status_code, r.text[:200])
                return False
            return True
        except (OSError, requests.RequestException) as e:
            self.logger.error("Mattermost report failed: %s", e)
            return False


def report(severity, title, body=None, state=None, source="observatory"):
    """Module-level one-shot for external callers who don't build an Observatory."""
    return Reporter(source=source).report(severity, title, body=body, state=state)


# --------------------------------------------------------------------------
# Race-guard primitives: heartbeat lease + emergency flag
# --------------------------------------------------------------------------
def _ensure_dir_for(path):
    d = os.path.dirname(path)
    if not d:
        return
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as e:
        logger.error("cannot create %s: %s", d, e)


def read_lease(path=LEASE_PATH):
    """Return the lease dict, or None if absent/unreadable."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def lease_is_fresh(lease, ttl=DEFAULT_LEASE_TTL):
    return bool(lease) and (time.time() - lease.get("heartbeat", 0) < ttl)


class LeaseBusy(Exception):
    """Raised when the lease is held fresh by another actor."""


class Lease:
    """Heartbeat advisory mutex. Use as a context manager:

        with Lease("close"):
            obs.park_mount(); obs.close_roof()

    Held only while the block runs; a background thread refreshes the heartbeat.
    A lease whose heartbeat is older than ttl is considered stale and steal-able,
    so a crashed/killed holder never deadlocks the other actor. The sentinel may
    pass force=True to preempt a live holder for a safety emergency."""

    def __init__(self, role, ttl=DEFAULT_LEASE_TTL, path=LEASE_PATH):
        self.role = role
        self.ttl = ttl
        self.path = path
        self._stop = threading.Event()
        self._thread = None

    def _write(self):
        _ensure_dir_for(self.path)
        data = {"role": self.role, "pid": os.getpid(),
                "host": socket.gethostname().split(".")[0],
                "acquired": getattr(self, "_acquired_ts", time.time()),
                "heartbeat": time.time()}
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, self.path)

    def acquire(self, force=False):
        cur = read_lease(self.path)
        if cur and not force and lease_is_fresh(cur, self.ttl) and cur.get("pid") != os.getpid():
            logger.info("lease held by %s (pid %s), not acquiring",
                        cur.get("role"), cur.get("pid"))
            return False
        if cur and lease_is_fresh(cur, self.ttl) and cur.get("pid") != os.getpid():
            logger.warning("forcibly stealing lease from %s (pid %s)",
                           cur.get("role"), cur.get("pid"))
        self._acquired_ts = time.time()
        self._write()
        self._stop.clear()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("lease acquired as '%s'", self.role)
        return True

    def _heartbeat_loop(self):
        interval = max(1, self.ttl // 3)
        while not self._stop.wait(interval):
            try:
                self._write()
            except OSError as e:
                logger.error("lease heartbeat failed: %s", e)

    def release(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        cur = read_lease(self.path)
        if cur and cur.get("pid") == os.getpid():
            try:
                os.remove(self.path)
            except OSError:
                pass
        logger.info("lease released ('%s')", self.role)

    def __enter__(self):
        if not self.acquire():
            raise LeaseBusy(f"lease held by another actor, '{self.role}' deferring")
        return self

    def __exit__(self, *exc):
        self.release()
        return False


def set_emergency(reason):
    """Sentinel-owned: raise the emergency flag (close beats open)."""
    _ensure_dir_for(EMERGENCY_PATH)
    try:
        with open(EMERGENCY_PATH, "w") as f:
            json.dump({"reason": reason, "ts": time.time(),
                       "host": socket.gethostname().split(".")[0]}, f)
        logger.warning("EMERGENCY raised: %s", reason)
    except OSError as e:
        logger.error("cannot raise emergency flag: %s", e)


def clear_emergency():
    """Sentinel-owned: clear once the observatory is safe and weather recovered."""
    try:
        os.remove(EMERGENCY_PATH)
        logger.info("emergency flag cleared")
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.error("cannot clear emergency flag: %s", e)


def is_emergency():
    return os.path.exists(EMERGENCY_PATH)


# --------------------------------------------------------------------------
# Observatory: direct-INDI + LX200 hardware control
# --------------------------------------------------------------------------
class Observatory:
    """Idempotent, verify-first, retried hardware operations.

    INDI control via indi_getprop/indi_setprop against `indi_host`. Authoritative
    mount state via the 10Micron LX200 API (host/port from config, default
    192.168.100.73:3490) - independent of the INDI server.
    """

    def __init__(self, indi_host, config, dry_run=False, reporter=None):
        self.indi_host = config.get("connections.indi_host", indi_host)
        self.config = config
        self.dry_run = dry_run
        self.reporter = reporter or Reporter()
        self.logger = logging.getLogger("observatory")

        self.cmd_timeout = config.get("timeouts.indi_command", 5)
        self.max_retries = int(config.get("safety.max_retries", 5))
        self.mount_park_timeout = config.get("timeouts.mount_park", 60)
        self.roof_close_timeout = config.get("timeouts.roof_close", 60)

        self.cap_close_timeout = config.get("timeouts.cap_close", 60)
        self.retry_delay = config.get("safety.retry_delay", 5)

        # Optional 10Micron LX200 enhancement (INDI-bypass). DISABLED unless
        # mount.lx200.host is configured, so the generic/public path is pure
        # INDI. Used judiciously: as the definitive confirm at the close-roof
        # precondition, and as a fallback when INDI is unreachable - never on
        # the routine polling path.
        self.lx200_host = config.get("indi.mount.lx200.host")
        self.lx200_port = int(config.get("indi.mount.lx200.port", 3490))
        self.lx200_gstat_parked = config.get("indi.mount.lx200.gstat_parked", "5#")
        self.lx200_enabled = bool(self.lx200_host)

    # ---- reporting passthrough ----
    def report(self, severity, title, body=None, state=None):
        return self.reporter.report(severity, title, body=body, state=state)

    # ---- low-level INDI ----
    def _run(self, cmd):
        try:
            return subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, universal_newlines=True,
                                  timeout=self.cmd_timeout, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.debug("cmd failed [%s] rc=%s err=%s", cmd, e.returncode, e.stderr.rstrip())
            return None
        except subprocess.TimeoutExpired:
            self.logger.warning("cmd timed out [%s]", cmd)
            return None

    def indi_get(self, prop):
        """Return the property value as a string, or None if missing/in-transition.
        A None return must never be read as a state - callers keep polling."""
        ws = self._run("indi_getprop -h {} -1 '{}'".format(self.indi_host, prop))
        if not ws:
            return None
        out = ws.stdout.rstrip()
        return out if out != "" else None

    def indi_set(self, prop, value):
        if self.dry_run:
            self.logger.info("[dry-run] would set %s=%s", prop, value)
            return True
        ws = self._run("indi_setprop -h {} '{}={}'".format(self.indi_host, prop, value))
        return bool(ws) and ws.returncode == 0

    # ---- mount LX200 (authoritative) ----
    def mount_lx200(self, command):
        """One-shot LX200 query to the mount (10Micron-specific INDI-bypass).
        Returns response string, or None if LX200 is not configured / fails.
        Sets Ultra-Precision mode first so GA/GZ come back as DD:MM:SS.SS."""
        if not self.lx200_enabled:
            return None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.cmd_timeout)
            s.connect((self.lx200_host, self.lx200_port))
            s.sendall(b"#:U2#")            # ultra precision (no reply)
            time.sleep(0.1)
            s.sendall(command.encode())
            time.sleep(0.3)
            resp = b""
            while b"#" not in resp:
                chunk = s.recv(128)
                if not chunk:
                    break
                resp += chunk
            s.close()
            return resp.decode("ascii", "ignore").strip()
        except OSError as e:
            self.logger.warning("LX200 %s failed: %s", command, e)
            return None

    # ---- state readers ----
    def is_parked(self):
        """Generic INDI parked check (the routine path): PARK switch On + tracking
        off + (if a park DEC is configured) DEC within offset. DEC is the stable
        equatorial axis - RA drifts for a parked mount, so it can't be checked.
        Conservative: anything unconfirmable returns False, so a roof close is
        never attempted over a mount we can't verify. If INDI is unreachable AND
        LX200 is configured, fall back to the definitive Gstat."""
        park = self.indi_get(self.config.get("indi.mount.park_property"))
        if park is None:
            if self.lx200_enabled:
                self.logger.warning("INDI park unreadable; falling back to LX200 Gstat")
                return self._lx200_parked()
            return False
        if park != self.config.get("indi.mount.park_setting"):
            return False
        track_prop = self.config.get("indi.mount.track_state_property")
        if track_prop:
            tr = self.indi_get(track_prop)
            if tr is not None and tr != self.config.get("indi.mount.track_state_setting"):
                return False
        dec_prop = self.config.get("indi.mount.coord_dec_property")
        park_dec = self.config.get("indi.mount.coord_dec_park_position")
        max_off = self.config.get("indi.mount.coord_dec_max_offset")
        if dec_prop and park_dec is not None and max_off is not None:
            dec = self.indi_get(dec_prop)
            if dec is None:
                return False  # in transition / unreadable -> not confirmed
            try:
                if abs(float(dec) - float(park_dec)) > float(max_off):
                    return False
            except ValueError:
                return False
        return True

    def _lx200_parked(self):
        """Definitive 10Micron parked state via LX200 Gstat (INDI-bypass)."""
        return self.lx200_enabled and self.mount_lx200("#:Gstat#") == self.lx200_gstat_parked

    def _parked_confirmed(self):
        """Strong confirm for the irreversible close-roof precondition: INDI says
        parked AND (when LX200 is configured) Gstat==5 agrees - Gstat 5 is also
        exactly when the mount releases its lock, which the dome interlock needs."""
        if not self.is_parked():
            return False
        return self._lx200_parked() if self.lx200_enabled else True

    def mount_altaz(self):
        """(alt_deg, az_deg) from the mount, or (None, None)."""
        return (_parse_dms(self.mount_lx200("#:GA#")), _parse_dms(self.mount_lx200("#:GZ#")))

    def is_roof_closed(self):
        val = self.indi_get(self.config.get("indi.dome.park_property"))
        return val == self.config.get("indi.dome.park_setting")

    def is_cap_closed(self):
        prop = self.config.get("indi.cap.property")
        if not prop:
            return True  # no cap configured -> treated as closed/safe
        return self.indi_get(prop) == self.config.get("indi.cap.setting")

    def is_weather_safe(self):
        prop = self.config.get("indi.weather.property")
        ok = self.config.get("indi.weather.ok_setting")
        stations = self.config.get("indi.weather.station_indexes", [1])
        if not prop:
            return True
        for st in stations:
            if self.indi_get("{}_{}".format(prop, st)) != ok:
                return False
        return True

    def cooler_power(self):
        """Cooler power percent as float, or None if not queryable (the cooler
        switch itself reads blank via indi_getprop; power is the observable proxy)."""
        prop = self.config.get("indi.camera.cooler_power_property")
        if not prop:
            return None
        val = self.indi_get(prop)
        try:
            return float(val) if val is not None else None
        except ValueError:
            return None

    # ---- helpers ----
    def _wait_until(self, predicate, timeout):
        """Poll predicate() once/sec until truthy or timeout. Returns final bool."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(1)
        return predicate()

    # ---- operations (idempotent, verify-first, command RE-ISSUED on retry) ----
    def park_mount(self):
        if self.is_parked():
            self.logger.info("mount already parked")
            return True
        prop = self.config.get("indi.mount.park_property")
        setting = self.config.get("indi.mount.park_setting")
        for attempt in range(1, self.max_retries + 1):
            self.logger.warning("park mount (attempt %d/%d)", attempt, self.max_retries)
            self.indi_set(prop, setting)                 # RE-ISSUE each attempt
            if self._wait_until(self.is_parked, self.mount_park_timeout):
                self.logger.info("mount parked")
                return True
            self.logger.warning("park did not complete (aborted mid-slew?), retrying")
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        return False

    def unpark_mount(self):
        if not self.is_parked():
            self.logger.info("mount already unparked")
            return True
        prop = self.config.get("indi.mount.unpark_property",
                               self.config.get("indi.mount.park_property"))
        unpark = self.config.get("indi.mount.unpark_setting", "Off")
        for attempt in range(1, self.max_retries + 1):
            self.logger.warning("unpark mount (attempt %d/%d)", attempt, self.max_retries)
            self.indi_set(prop, unpark)
            if self._wait_until(lambda: not self.is_parked(), self.mount_park_timeout):
                return True
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        return False

    def close_roof(self):
        if self.is_roof_closed():
            self.logger.info("roof already closed")
            return True
        # SAFETY precondition: never close over a mount that is not fully parked.
        # _parked_confirmed() requires INDI-parked and (if LX200 configured)
        # Gstat==5 - which is also exactly when the mount releases its lock, so
        # the dome Mount Policy interlock will accept the park.
        if not self._parked_confirmed():
            self.logger.critical("refusing to close roof: mount not confirmed parked")
            return False
        prop = self.config.get("indi.dome.park_property")
        setting = self.config.get("indi.dome.park_setting")
        for attempt in range(1, self.max_retries + 1):
            self.logger.warning("close roof (attempt %d/%d)", attempt, self.max_retries)
            self.indi_set(prop, setting)                 # RE-ISSUE each attempt
            if self._wait_until(self.is_roof_closed, self.roof_close_timeout):
                self.logger.info("roof closed")
                return True
            # If a transient race recurred, re-confirm the mount is still parked
            # before re-commanding the dome.
            if not self._parked_confirmed():
                self.logger.critical("mount no longer parked during roof close - aborting")
                return False
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        return False

    def open_roof(self):
        if not self.is_roof_closed():
            self.logger.info("roof already open")
            return True
        prop = self.config.get("indi.dome.unpark_property",
                               self.config.get("indi.dome.park_property"))
        unpark = self.config.get("indi.dome.unpark_setting", "Off")
        for attempt in range(1, self.max_retries + 1):
            self.logger.warning("open roof (attempt %d/%d)", attempt, self.max_retries)
            self.indi_set(prop, unpark)
            if self._wait_until(lambda: not self.is_roof_closed(), self.roof_close_timeout):
                return True
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        return False

    def close_cap(self):
        prop = self.config.get("indi.cap.property")
        if not prop:
            self.logger.debug("no cap configured - skipping close_cap")
            return True
        setting = self.config.get("indi.cap.setting")
        for attempt in range(1, self.max_retries + 1):
            self.logger.warning("close cap (attempt %d/%d)", attempt, self.max_retries)
            self.indi_set(prop, setting)
            if self._wait_until(self.is_cap_closed, self.cap_close_timeout):
                return True
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        return False

    def cooler_off(self):
        """Switch the TEC/fan off, then VERIFY via cooler power -> ~0 (the
        COOLER_OFF switch reads blank, so power is the observable check)."""
        prop = self.config.get("indi.camera.cooler_property")
        setting = self.config.get("indi.camera.cooler_setting")
        if not prop:
            self.logger.debug("no cooler property configured - skipping")
            return True
        for attempt in range(1, self.max_retries + 1):
            self.indi_set(prop, setting)
            power = self.cooler_power()
            if power is None:
                self.logger.warning("cooler_off sent; cannot verify (no power property) - trusting")
                return True
            if self._wait_until(lambda: (self.cooler_power() or 0) <= 1.0, 30):
                self.logger.info("cooler off verified (power ~0%%)")
                return True
            self.logger.warning("cooler still drawing power (%.0f%%), retrying", power)
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        return False

    def warm_camera(self, target_c, slope_c_per_min=5, ramp_threshold=0.2):
        """Start a gentle warm ramp to a target above ambient (drives TEC to 0).
        Fire-and-set: the wait for the setpoint is the caller's concern."""
        dev = self.config.get("indi.camera.device")
        if not dev:
            self.logger.debug("no camera device configured - skipping warm")
            return True
        ok = self.indi_set("{}.CCD_TEMP_RAMP.RAMP_SLOPE".format(dev), slope_c_per_min)
        ok &= self.indi_set("{}.CCD_TEMP_RAMP.RAMP_THRESHOLD".format(dev), ramp_threshold)
        ok &= self.indi_set("{}.CCD_TEMPERATURE.CCD_TEMPERATURE_VALUE".format(dev), target_c)
        return ok

    def state_snapshot(self):
        """Live readings for state-aware reports."""
        alt, az = self.mount_altaz()
        return {"parked": self.is_parked(), "roof_closed": self.is_roof_closed(),
                "weather_safe": self.is_weather_safe(), "cooler_power": self.cooler_power(),
                "alt": alt, "az": az}

    # ---- multi-night bootstrap layers (POSTPONED - stubs only) ----
    def ensure_kstars(self):
        raise NotImplementedError("multi-night bootstrap layer 1 (launch KStars) - postponed")

    def ensure_ekos(self):
        raise NotImplementedError("multi-night bootstrap layer 2 (start Ekos profile) - postponed")


def _parse_dms(resp):
    """Parse a 10Micron DD:MM:SS.SS / DDD:MM:SS.SS (or DD*MM) response to degrees."""
    if not resp:
        return None
    s = resp.replace("#", "").strip()
    neg = s.startswith("-")
    s = s.lstrip("+-")
    try:
        sep = ":" if ":" in s else ("*" if "*" in s else None)
        if sep:
            parts = s.split(sep)
            deg = float(parts[0])
            deg += float(parts[1]) / 60 if len(parts) > 1 else 0
            deg += float(parts[2]) / 3600 if len(parts) > 2 else 0
        else:
            deg = float(s)
        return -deg if neg else deg
    except (ValueError, IndexError):
        return None


if __name__ == "__main__":
    # Quick state dump for debugging: observatorylib.py <config> [indi_host]
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = ObservatoryConfig(sys.argv[1] if len(sys.argv) > 1 else "ekos_sentinel_config_production.yaml")
    host = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    obs = Observatory(host, cfg)
    print(json.dumps(obs.state_snapshot(), indent=2, default=str))
