import js from '@eslint/js'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // PRIVACY BOUNDARY: demographic types/data exist only in lib/api/review.ts
    // and lib/api/types/review.ts, renderable only inside features/reviewBoard/.
    // Everything else — especially student routes — must not import them.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/features/reviewBoard/**', 'src/lib/api/review.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/api/review', '**/api/types/review', '**/types/review'],
              message:
                'Demographic review types may only be imported inside features/reviewBoard/. ' +
                'This is the privacy boundary from CLAUDE.md invariant 1.',
            },
          ],
        },
      ],
    },
  },
)
