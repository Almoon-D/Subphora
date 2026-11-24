// Copyright (c) 2026 Almoon-D. All rights reserved.
// ESLint with type information. typescript-eslint reads TypeScript 6.0 (the newest it
// supports); `npm run typecheck` checks the types with TypeScript 7 (decision 0016).
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "test-results", "playwright-report"] },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  reactHooks.configs.flat["recommended-latest"],
  {
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: ["eslint.config.js"],
    extends: [tseslint.configs.disableTypeChecked],
    languageOptions: { globals: { ...globals.node } },
  },
);
