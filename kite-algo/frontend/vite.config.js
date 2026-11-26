import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser only ever talks to the Vite dev server (port 5173).
// Anything starting with /api is forwarded to the FastAPI backend, so there
// are no CORS problems and the backend address lives in one place.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      // live ticks: the browser talks to the dev server, which forwards the websocket to the backend
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
});
