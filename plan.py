import os, json, datetime
SLOTS = {1: (9, 0), 2: (14, 0), 3: (19, 0)}   # IST start times
CUTOFF = (22, 30)
now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
today = now.strftime("%Y-%m-%d")
ev, inp = os.environ.get("EVENT_NAME", ""), os.environ.get("INPUT_SLOT", "").strip()
slot = ""
if ev == "workflow_dispatch":
    slot = inp or "1"
else:
    try: h = json.load(open("history.json"))
    except Exception: h = {}
    done = h.get("done", {}).get(today, []); tries = h.get("tries", {}).get(today, {})
    if (now.hour, now.minute) <= CUTOFF:
        for s, (hh, mm) in SLOTS.items():
            if (now.hour, now.minute) >= (hh, mm) and s not in done and int(tries.get(str(s), 0)) < 3:
                slot = str(s); break
print("slot:", slot or "none", "| IST", now.strftime("%H:%M"))
with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f: f.write(f"slot={slot}\n")
