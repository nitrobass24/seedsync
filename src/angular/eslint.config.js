// @ts-check
// All rules are at "error". See #376-#382 for the cleanup history.
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
      // Rules required by #376; most graduated to "error" in targeted cleanup PRs:
      "@angular-eslint/prefer-on-push-component-change-detection": "error",
      "@angular-eslint/no-empty-lifecycle-method": "error",
      "@typescript-eslint/no-explicit-any": "error",
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
      // A11y rules graduated to "error" in #380/#381 cleanup:
      "@angular-eslint/template/click-events-have-key-events": "error",
      "@angular-eslint/template/interactive-supports-focus": "error",
      "@angular-eslint/template/alt-text": "error",
      // Graduated to "error" in #378 after the codebase was cleaned up.
      "@angular-eslint/template/eqeqeq": "error",
    },
  },
]);
