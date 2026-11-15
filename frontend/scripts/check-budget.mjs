// Fails the build if gzipped JS exceeds the budget (fonts and CSS excluded).
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const BUDGET_KB = 30;
const dir = "dist/assets";
const total = readdirSync(dir)
  .filter((f) => f.endsWith(".js"))
  .reduce((sum, f) => sum + gzipSync(readFileSync(join(dir, f))).length, 0);
const kb = total / 1024;
console.log(`JS gzipped: ${kb.toFixed(1)} KB (budget ${BUDGET_KB} KB)`);
if (kb > BUDGET_KB) process.exit(1);
