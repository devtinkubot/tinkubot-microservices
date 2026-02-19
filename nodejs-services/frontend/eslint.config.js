const js = require("@eslint/js");

module.exports = [
  {
    ignores: [
      "node_modules/**",
      "apps/admin-dashboard/dist/**",
      "*.min.js",
      "**/*.map",
      "**/*.ts",
      "**/*.tsx",
    ],
  },
  js.configs.recommended,
  {
    files: ["**/*.js", "**/*.cjs", "**/*.mjs"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        process: "readonly",
        __dirname: "readonly",
        module: "readonly",
        require: "readonly",
        console: "readonly",
        Buffer: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
      },
    },
    rules: {
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
];
