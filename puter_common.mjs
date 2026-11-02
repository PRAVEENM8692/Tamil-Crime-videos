// Shared helpers for the Puter.js scripts (voices and pictures).
import { init } from "@heyputer/puter.js/src/init.cjs";

export function getPuter() {
  if (!process.env.PUTER_AUTH_TOKEN) throw new Error("PUTER_AUTH_TOKEN is not set");
  return init(process.env.PUTER_AUTH_TOKEN);
}

// Puter can hand back a Buffer, ArrayBuffer, Blob-like, or an element with .src (data: URL or http URL).
export async function toBuffer(r) {
  if (!r) throw new Error("empty result");
  if (Buffer.isBuffer(r)) return r;
  if (r instanceof ArrayBuffer) return Buffer.from(r);
  if (typeof r.arrayBuffer === "function") return Buffer.from(await r.arrayBuffer());
  const src = r.src || r.url || r.currentSrc || (typeof r === "string" ? r : null);
  if (typeof src === "string") {
    if (src.startsWith("data:")) return Buffer.from(src.split(",")[1], "base64");
    const resp = await fetch(src);
    if (!resp.ok) throw new Error("download failed " + resp.status);
    return Buffer.from(await resp.arrayBuffer());
  }
  throw new Error("unknown result shape: " + Object.keys(r).slice(0, 8).join(","));
}

export const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
