module.exports = {
  root: true,
  env: { browser: true, es2021: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["react-hooks", "react-refresh", "@typescript-eslint"],
  rules: {
    "react-hooks/rules-of-hooks": "error",
    "react-refresh/only-export-components": "warn",
  },
  ignorePatterns: ["dist", "node_modules"],
};
