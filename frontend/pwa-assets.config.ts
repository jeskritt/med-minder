import {
  defineConfig,
  minimal2023Preset,
} from "@vite-pwa/assets-generator/config";

// Generates the committed icon set (pwa-192/512, maskable, apple-touch,
// favicon) from one source asset. Run via `pnpm generate-pwa-assets`.
export default defineConfig({
  headLinkOptions: { preset: "2023" },
  preset: minimal2023Preset,
  images: ["public/medminder.svg"],
});
