#!/usr/bin/env python3
"""Unit test: Reporter one-liner/mention/state-block + shutdown marker.
No network - requests.post is monkeypatched. Run: python3 test_reporter.py"""
import os, sys, tempfile, json
EKOS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EKOS)
import observatorylib as obs

PASS=[0]; FAIL=[0]
def check(n,c): print(("PASS " if c else "FAIL ")+n); (PASS if c else FAIL)[0]+=1

captured=[]
class FakeResp: status_code=200; text="ok"
def fake_post(url, data=None, timeout=None):
    captured.append(json.loads(data["payload"])["text"]); return FakeResp()
obs.requests.post = fake_post

tmp=tempfile.mkdtemp()
urlf=os.path.join(tmp,"hook"); open(urlf,"w").write("http://example/hook\n")

r = obs.Reporter(url_file=urlf, mention="@hans")
r.report("info","cooling to -10")
r.report("critical","roof did not close", state={"mount_parked":True,"roof_closed":False})
r.report("warn","weather unsafe")
info_txt, crit_txt, warn_txt = captured

check("info is one line", "\n" not in info_txt)
check("info has NO mention", "@hans" not in info_txt)
check("info has NO code block", "```" not in info_txt)
check("info carries source tag", "[observatory]" in info_txt)
check("critical HAS mention", "@hans" in crit_txt)
check("critical WITH state renders a code block", "```" in crit_txt and "mount_parked: True" in crit_txt)
check("warn HAS mention", "@hans" in warn_txt)
check("warn WITHOUT state is one line, no block", "\n" not in warn_txt and "```" not in warn_txt)

captured.clear()
obs.Reporter(url_file=urlf, mention=None).report("critical","x")
check("mention=None -> no @ leaked", "@" not in captured[0])

obs.SHUTDOWN_MARK_PATH = os.path.join(tmp,"shutdown_complete")
check("marker absent initially", not obs.is_shutdown_complete())
obs.mark_shutdown_complete()
check("marker set after mark", obs.is_shutdown_complete())
obs.clear_shutdown_complete()
check("marker cleared", not obs.is_shutdown_complete())

print("\n{} passed, {} failed".format(PASS[0],FAIL[0]))
sys.exit(1 if FAIL[0] else 0)
