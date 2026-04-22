// @ts-check
// TODO(#376): Many rules below are intentionally set to "warn" (not "error")
// to keep the initial lint step non-fatal while the tooling PR lands. A
// follow-up cleanup PR should graduate these to "error" and address the
// accumulated findings (e.g. `ChangeDetectionStrategy.OnPush`,
// inject() migration, ==/===, inferrable types, empty functions,
// Array<T> vs T[]).
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
      // Rules required by #376; most remain "warn" while targeted cleanups graduate to "error":
      "@angular-eslint/prefer-on-push-component-change-detection": "warn",
      "@angular-eslint/no-empty-lifecycle-method": "warn",
      "@typescript-eslint/no-explicit-any": "error",
      // "no-unused-vars" is the one rule #376 asks to keep as "error":
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // High-volume stylistic findings — demoted to "warn" per the task
      // plan so CI stays green. Follow-up cleanup tracked in #376.
      "@typescript-eslint/no-inferrable-types": "warn",
      "@typescript-eslint/no-empty-function": "warn",
      "@typescript-eslint/array-type": "warn",
      "@typescript-eslint/consistent-indexed-object-style": "warn",
      "@angular-eslint/prefer-inject": "warn",
      "prefer-const": "warn",
    },
  },
  {
    files: ["**/*.html"],
    extends: [
      angular.configs.templateRecommended,
      angular.configs.templateAccessibility,
    ],
    rules: {
      // A11y rules graduated to "error" in #380/#381 cleanup:
      "@angular-eslint/template/click-events-have-key-events": "error",
      "@angular-eslint/template/interactive-supports-focus": "error",
      "@angular-eslint/template/alt-text": "error",
      // High-volume template findings — demoted to "warn" for this PR.
      // Follow-up cleanup tracked in #376.
      "@angular-eslint/template/eqeqeq": "warn",
    },
  },
]);
