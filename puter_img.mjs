// Makes one picture with Puter.js. Usage: node puter_img.mjs prompt.txt out.img
// Model: PUTER_IMG_MODEL (default google/gemini-2.5-flash-image). Exit 0 only on success.
import fs from "node:fs";
import { getPuter, toBuffer } from "./puter_common.mjs";

try {
  const [promptFile, outFile] = process.argv.slice(2);
  const puter = getPuter();
  const prompt = fs.readFileSync(promptFile, "utf8");
  const r = await puter.ai.txt2img(prompt, { model: process.env.PUTER_IMG_MODEL || "google/gemini-2.5-flash-image" });
  const buf = await toBuffer(r);
  if (buf.length < 5000) throw new Error("image too small");
  fs.writeFileSync(outFile, buf);
  console.log("OK");
  process.exit(0);
} catch (e) {
  console.log("FAIL " + String((e && e.message) || e).slice(0, 300));
  process.exit(1);
}
