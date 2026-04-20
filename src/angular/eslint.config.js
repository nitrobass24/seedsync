// @ts-check
// TODO(#376): Many rules below are intentionally set to "warn" (not "error")
// to keep the initial lint step non-fatal while the tooling PR lands. A
// follow-up cleanup PR should graduate these to "error" and address the
// accumulated findings (e.g. `ChangeDetectionStrategy.OnPush`, a11y on
// interactive elements, <img> alt text, `any` casts).
// See: https://github.com/nitrobass24/seedsync/issues/376
const eslint = require("@eslint/js");
const { defineConfig } = require("eslint/config");
const tseslint = require("typescript-eslint");
const angular = require("angular-eslint");

module.exports = defineConfig([
  {
    files: ["**/*.ts"],
    extends: [
      eslint.configs.recommended,
      tseslint.configs.recommended,
      tseslint.configs.stylistic,
      angular.configs.tsRecommended,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      "@angular-eslint/directive-selector": [
        "error",
        {
          type: "attribute",
          prefix: "app",
          style: "camelCase",
        },
      ],
      "@angular-eslint/component-selector": [
        "error",
        {
          type: "element",
          prefix: "app",
          style: "kebab-case",
        },
      ],
      // Rules required by #376, all "warn" for the initial PR:
      "@angular-eslint/prefer-on-push-component-change-detection": "warn",
      "@angular-eslint/no-empty-lifecycle-method": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
      // "no-unused-vars" is the one rule #376 asks to keep as "error":
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // Graduated to "error" in #378 after the codebase was cleaned up.
      "@typescript-eslint/no-inferrable-types": "error",
      "@typescript-eslint/no-empty-function": "error",
      "@typescript-eslint/array-type": "error",
      "@typescript-eslint/consistent-indexed-object-style": "error",
      "@angular-eslint/prefer-inject": "error",
      "prefer-const": "error",
    },
  },
  {
    files: ["**/*.html"],
    extends: [
      angular.configs.templateRecommended,
      angular.configs.templateAccessibility,
    ],
    rules: {
      // Required-by-#376 a11y rules, "warn" for the initial PR:
      "@angular-eslint/template/click-events-have-key-events": "warn",
      "@angular-eslint/template/interactive-supports-focus": "warn",
      // High-volume template findings — demoted to "warn" for this PR.
      // Follow-up cleanup tracked in #376.
      "@angular-eslint/template/alt-text": "warn",
      // Graduated to "error" in #378 after the codebase was cleaned up.
      "@angular-eslint/template/eqeqeq": "error",
    },
  },
]);
