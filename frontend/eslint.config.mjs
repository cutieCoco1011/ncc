export default [
  {
    ignores: [".next/**", "node_modules/**"]
  },
  {
    files: ["app/**/*.{js,jsx,mjs}", "lib/**/*.mjs", "tests/**/*.mjs"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: {
          jsx: true
        }
      },
      globals: {
        React: "readonly",
        window: "readonly",
        fetch: "readonly",
        console: "readonly"
      }
    },
    rules: {
      "no-undef": "error",
      "no-unused-vars": "off"
    }
  }
];
