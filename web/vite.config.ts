import tailwindcss from "@tailwindcss/vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact from "@vitejs/plugin-react";
import { nitro } from "nitro/vite";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

import { loadEnvFiles } from "./src/lib/env";

loadEnvFiles();

const repositoryRoot = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  server: {
    port: 3000,
    fs: {
      allow: [repositoryRoot],
    },
  },
  resolve: {
    tsconfigPaths: true,
  },
  plugins: [
    tailwindcss(),
    tanstackStart({
      srcDirectory: "src",
    }),
    viteReact(),
    nitro(),
  ],
});
