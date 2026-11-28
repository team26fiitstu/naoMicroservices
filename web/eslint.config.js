import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // shadcn/ui components also export cva variants
      'react-refresh/only-export-components': ['error', { allowExportNames: ['buttonVariants', 'badgeVariants'] }],
      // one radius from theme, sizes would drift apart again
      'no-restricted-syntax': ['error', ...['Literal[value', 'TemplateElement[value.raw'].map((node) => ({
        selector: `${node}=/(^|\\s|:)rounded(-(sm|md|lg|xl|2xl|3xl))?(\\s|$)/]`,
        message: 'Use rounded-base, or rounded-full for circles.',
      }))],
    },
  },
])
