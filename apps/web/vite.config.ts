import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // Suppress ECONNRESET noise when the API restarts or isn't running yet
        configure: (proxy) => {
          proxy.on("error", (err, _req, _res) => {
            // ECONNRESET / ECONNREFUSED are expected when the API is down or
            // reloading.  Log a one-liner instead of a full stack trace.
            const code = (err as NodeJS.ErrnoException).code ?? "";
            if (code === "ECONNRESET" || code === "ECONNREFUSED") {
              console.warn(`[proxy] API unreachable (${code}) — retrying on next request`);
            } else {
              console.error("[proxy] unexpected error:", err.message);
            }
          });
        },
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
        // Same suppression for WebSocket proxy resets
        configure: (proxy) => {
          proxy.on("error", (err) => {
            const code = (err as NodeJS.ErrnoException).code ?? "";
            if (code !== "ECONNRESET" && code !== "ECONNREFUSED") {
              console.error("[ws-proxy] unexpected error:", err.message);
            }
          });
        },
      },
    },
  },
});
