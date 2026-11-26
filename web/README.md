# Web

React, TypeScript, Vite, Tailwind, shadcn/ui.

## Run

```sh
npm ci
npm run dev
```

Requests go to the backend through the Vite proxy (`vite.config.ts`), so the services must be running on ports 7000, 7001, 5000, 8000 and 9901, for example via Docker Compose from the repository root.

## Check

```sh
npm run lint
npm run build
```

`build` also runs the TypeScript check.

## Environment

- `VITE_API_BASE`: backend URL, empty means same origin.
- `VITE_LLM_API_BASE`, `VITE_LLM_API_KEY`: LLM endpoint and key. Without the key, the calorie estimate and exercise description are off and voice commands use keyword matching.

## Structure

- `pages/`: one file per route.
- `components/ui/`: shared UI components.
- `components/layout/`: page and navigation.
- `components/editor/`, `components/exercise/`, `components/voice/`: feature components.
- `hooks/`: React hooks.
- `lib/`: API calls and helpers without UI.
