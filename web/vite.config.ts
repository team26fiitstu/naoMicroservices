import path from "path";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { nodePolyfills } from 'vite-plugin-node-polyfills';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), nodePolyfills({
      include: ['crypto', 'stream', 'buffer'],
    })],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // translator
      "/exercise/from_video": { target: "http://localhost:7000", changeOrigin: true },
      "/exercise/from_image": { target: "http://localhost:7000", changeOrigin: true },
      "^/exercise/[^/]+/run$": { target: "http://localhost:7000", changeOrigin: true },
      "^/choreography/[^/]+/run$": { target: "http://localhost:7000", changeOrigin: true },
      "^/run(?:/|$)": { target: "http://localhost:7000", changeOrigin: true },
      // robot: must be above "/voiceLines"
      "/voiceLines/applyVoiceLine": { target: "http://localhost:5000", changeOrigin: true },
      // exercise config service
      "/voiceLines": { target: "http://localhost:7001", changeOrigin: true },
      "/exercise": { target: "http://localhost:7001", changeOrigin: true },
      "/choreography": { target: "http://localhost:7001", changeOrigin: true },
      // voice command API
      "/command": { target: "http://localhost:8000", changeOrigin: true },
      "/pose": { target: "http://localhost:8000", changeOrigin: true },
      // audio to text
      "/translate": { target: "http://localhost:9901", changeOrigin: true },
    },
  },
});
