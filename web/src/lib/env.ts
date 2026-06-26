import * as fs from "fs";
import * as path from "path";

/**
 * Load env files for Vite/Nitro config in the same broad priority shape that
 * the old Next app expected. Earlier files win so local overrides remain local.
 */
export function loadEnvFiles() {
  const nodeEnv = process.env.NODE_ENV || "development";
  const files = [".env.local", `.env.${nodeEnv}`, ".env"];

  for (const file of files) {
    const envPath = path.resolve(file);
    if (!fs.existsSync(envPath)) continue;

    const content = fs.readFileSync(envPath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;

      const eqIndex = trimmed.indexOf("=");
      if (eqIndex === -1) continue;

      const key = trimmed.slice(0, eqIndex).trim();
      let value = trimmed.slice(eqIndex + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }

      if (!process.env[key]) {
        process.env[key] = value;
      }
    }
  }
}
