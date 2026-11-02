// Speaks many lines with Puter.js (Gemini TTS). Usage: node puter_tts.mjs jobs.json
// jobs.json = [{ "text": "...", "out": "file.raw", "voice": "Puck", "instructions": "cheerful little boy" }, ...]
// Writes each audio to its "out" file. Prints one line per job ("OK id" or "FAIL id reason").
// Exit code 0 only if every job worked. Needs the PUTER_AUTH_TOKEN secret.
import fs from "node:fs";
import { getPuter, toBuffer, sleep } from "./puter_common.mjs";

const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let failed = 0;
try {
  const puter = getPuter();
  for (let i = 0; i < jobs.length; i++) {
    const j = jobs[i];
    let ok = false, last = "";
    for (let a = 0; a < 3 && !ok; a++) {
      try {
        const opts = { provider: "gemini", voice: j.voice || "Puck", language: "ta-IN" };
        if (process.env.PUTER_TTS_MODEL) opts.model = process.env.PUTER_TTS_MODEL;
        if (j.instructions) opts.instructions = j.instructions;
        const r = await puter.ai.txt2speech(j.text, opts);
        const buf = await toBuffer(r);
        if (buf.length < 1000) throw new Error("audio too small");
        fs.writeFileSync(j.out, buf);
        ok = true;
      } catch (e) {
        last = String((e && e.message) || e).slice(0, 200);
        await sleep(2500 * (a + 1));
      }
    }
    console.log(ok ? `OK ${i}` : `FAIL ${i} ${last}`);
    if (!ok) failed++;
    await sleep(700);   // be gentle with the rate limit
  }
} catch (e) {
  console.log("FATAL " + String((e && e.message) || e).slice(0, 300));
  failed = jobs.length || 1;
}
process.exit(failed ? 1 : 0);   // Puter keeps sockets open, so exit explicitly
