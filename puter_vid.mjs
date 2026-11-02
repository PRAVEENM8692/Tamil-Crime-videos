// Makes AI video clips with Puter.js (puter.ai.txt2vid). Usage: node puter_vid.mjs jobs.json
// jobs.json = [{ "id": 0, "prompt": "...", "image": "first_frame.jpg" or "", "out": "clip.mp4", "seconds": 5, "model": "wan-ai/wan2.7-i2v" }, ...]
// Prints "OK id" / "FAIL id reason" per job. Always exits 0; the caller checks which files exist.
// Settings: VID_CONCURRENCY (default 3), VIDEO_SIZE (default 720P), VIDEO_TEST=true (sample clip, spends no credits).
import fs from "node:fs";
import { getPuter, toBuffer, sleep } from "./puter_common.mjs";

const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const CONC = Math.max(1, parseInt(process.env.VID_CONCURRENCY || "3", 10));
let outOfMoney = false, next = 0;

async function runJob(puter, j) {
  const opts = { model: j.model, seconds: j.seconds, generate_audio: false };
  const size = process.env.VIDEO_SIZE || "720P";   // VIDEO_SIZE=none leaves the size to the model
  if (size !== "none") opts.size = size;
  if (process.env.VIDEO_TEST === "true") opts.test_mode = true;
  if (j.image) {
    const b64 = fs.readFileSync(j.image).toString("base64");
    opts.input_reference = "data:image/jpeg;base64," + b64;
  }
  let last = "";
  for (let a = 0; a < 3; a++) {
    if (outOfMoney) return console.log(`FAIL ${j.id} skipped (no Puter credits)`);
    try {
      const r = await puter.ai.txt2vid(j.prompt, opts);
      const buf = await toBuffer(r);
      if (buf.length < 20000) throw new Error("clip too small");
      fs.writeFileSync(j.out, buf);
      return console.log(`OK ${j.id}`);
    } catch (e) {
      last = String((e && (e.code || e.message)) || e).slice(0, 200) + " " + String((e && e.message) || "").slice(0, 120);
      if (/insufficient_funds/.test(last)) { outOfMoney = true; break; }
      if (/moderation|bad_request|prompt_required/.test(last)) break;   // retrying will not help
      await sleep(4000 * (a + 1));
    }
  }
  console.log(`FAIL ${j.id} ${last}`);
}

try {
  const puter = getPuter();
  await Promise.all(Array.from({ length: CONC }, async () => {
    while (next < jobs.length) { const j = jobs[next++]; await runJob(puter, j); }
  }));
} catch (e) {
  console.log("FATAL " + String((e && e.message) || e).slice(0, 300));
}
process.exit(0);   // Puter keeps sockets open
