import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  globalIgnores(["dist", "src/routeTree.gen.ts"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true, allowExportNames: ["Route"] },
      ],
    },
  },
  {
    // TanStack file-route modules must co-export `Route` + a component,
    // and `ui/button.tsx` co-exports the `buttonVariants` cva constant
    // (shadcn pattern). Fast Refresh granularity is not meaningful for
    // these, so the rule is intentionally off here rather than fought
    // with file splits.
    files: ["src/routes/**/*.tsx", "src/components/ui/button.tsx"],
    rules: {
      "react-refresh/only-export-components": "off",
    },
  },
]);
