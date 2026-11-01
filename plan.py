"""Slot planner (stdlib only). Picks which of the 2 daily videos should be made now."""
import os, json, datetime
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
SLOTS = {1: (12, 0), 2: (18, 0)}          # IST start times: 12:00 mystery/murder, 18:00 heist/fraud
CUTOFF = (23, 30)

def out(slot):
    p = os.environ.get("GITHUB_OUTPUT")
    line = f"slot={slot}\n"
    if p: open(p, "a").write(line)
    print("PLAN:", slot or "(nothing to do)")

now = datetime.datetime.now(IST); today = now.strftime("%Y-%m-%d")
if os.environ.get("EVENT_NAME") == "workflow_dispatch":
    s = (os.environ.get("INPUT_SLOT") or "1").strip()
    out(s if s in ("1", "2") else "1"); raise SystemExit
try: h = json.load(open("history.json"))
except Exception: h = {}
done = h.get("done", {}).get(today, []); tries = h.get("tries", {}).get(today, {})
if (now.hour, now.minute) >= CUTOFF: out(""); raise SystemExit
for s, (hh, mm) in sorted(SLOTS.items()):
    if (now.hour, now.minute) >= (hh, mm) and s not in done and int(tries.get(str(s), 0)) < 3:
        out(s); raise SystemExit
out("")
