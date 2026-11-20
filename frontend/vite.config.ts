import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tanstackRouter(),
    react(),
    tailwindcss(),
    // PWA (Phase 8): an authored service worker (src/sw.ts) via injectManifest
    // so the Phase 7 push/notificationclick logic is preserved while Workbox
    // precaches the app shell. Registration is manual (lib/pwa.ts), so the
    // UpdatePrompt can offer a controlled refresh (no auto-reload loop).
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      registerType: "prompt",
      injectRegister: false,
      manifest: {
        name: "MedMinder",
        short_name: "MedMinder",
        description: "Track your medications, doses, and reminders.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        theme_color: "#0f172a",
        background_color: "#f8fafc",
        icons: [
          { src: "/pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "/pwa-512x512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/maskable-icon-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      injectManifest: {
        // Precache the built static shell only. API responses are never
        // listed here, so no medical data is ever cached (FR-006/SC-004).
        globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
      },
      devOptions: {
        enabled: true,
        type: "module",
        navigateFallback: "index.html",
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // Cross-platform dev: the container runs Linux while the source is
    // bind-mounted from a Windows/macOS host, where inotify events don't
    // cross the boundary. Poll so HMR sees host edits.
    watch: { usePolling: true },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  envDir: "../",
});
