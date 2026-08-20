# TinyMRP frontend

The React/Vite application behind TinyMRP's part detail, BOM and visual list
pages. It is not a separate product and does not run on its own: `vite build`
compiles it straight into `app/static/parts-ui/`, which Flask then serves.

**The compiled output is committed.** Deploying TinyMRP therefore needs no
Node.js at all — only work on the frontend itself does.

## Working on it

```bash
cd frontend
npm install
npm run dev      # hot reload against a Flask backend on :5000
npm run build    # writes ../app/static/parts-ui/ — commit the result
```

| Script | Does |
| --- | --- |
| `npm run dev` | Vite dev server with hot module replacement |
| `npm run build` | Production build into `../app/static/parts-ui/` |
| `npm run lint` | ESLint over the whole package |
| `npm test` | Vitest unit tests, once |
| `npm run test:watch` | Vitest in watch mode |
| `npm run test:coverage` | Vitest with coverage |
| `npm run test:e2e` | Playwright end-to-end tests |

Because the build is committed, a change here is only finished once
`npm run build` has been run and `app/static/parts-ui/` is committed with it.
Otherwise the running application keeps serving the previous bundle.

## Where the rest is

- Running the whole stack from a checkout, backend included:
  [`docs/deployment/09-local-development.md`](../docs/deployment/09-local-development.md)
- What the pages do, from a user's point of view: the in-app Help, built from
  [`docs/help/`](../docs/help/)
