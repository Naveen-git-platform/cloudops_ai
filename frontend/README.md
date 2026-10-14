# CloudOps AI — Frontend

Dashboard for CloudOps AI, built with Next.js (App Router), TypeScript, Tailwind CSS and Motion for React (`motion`, imported from `motion/react`).

## Data sources

| Dashboard section                                   | Source                                     |
| --------------------------------------------------- | ------------------------------------------ |
| Service health                                      | **Live**: `GET /services`, `GET /integrations` |
| Overview: system status, services healthy, degraded | **Live**: derived from `GET /services`     |
| Incidents, recent activity, system health chart     | Demo data (`lib/demo-data.ts`)             |
| Recent deployments, incident and deployment counts  | Demo data (`lib/demo-data.ts`)             |

Demo sections are labelled **Demo data** in the UI. They switch to the API once their backend endpoints exist.

## Requirements

- Node.js 20.9+ (developed on Node 22)
- The CloudOps backend running for live data (see `../backend/README.md`). The dashboard still renders without it and shows an error state with a Retry button.

## Getting started

From the `frontend/` directory:

```bash
cp .env.example .env.local   # then adjust if your backend isn't on 127.0.0.1:8000
npm install
npm run dev
```

Open http://localhost:3000.

## Configuration

| Variable           | Default                 | Description                                   |
| ------------------ | ----------------------- | --------------------------------------------- |
| `CLOUDOPS_API_URL` | `http://127.0.0.1:8000` | Base URL of the CloudOps FastAPI backend      |

`CLOUDOPS_API_URL` is read on the Next.js server only. The browser never calls the backend directly, so it is not exposed to clients and the backend needs no CORS setup. It can point at an internal hostname (for example `http://cloudops-api:8000` in a container network).

The variable is read at request time, so the same production build works against any backend; set it in the environment of `npm start` (or your host).

## Scripts

| Command         | Purpose                         |
| --------------- | ------------------------------- |
| `npm run dev`   | Start the dev server            |
| `npm run lint`  | Run ESLint                      |
| `npm run build` | Production build + type check   |
| `npm start`     | Serve the production build      |

`npm run build` does not contact the backend: the page is partially prerendered, and live data is fetched per request.

## How live data loads

1. `app/page.tsx` calls `loadServiceRegistry()` from `lib/api.ts` without awaiting it.
2. The promise streams to client components, which read it with React's `use()` inside `<Suspense>` boundaries. Each live section shows a skeleton while loading.
3. `loadServiceRegistry()` never throws. If the API is unreachable (5 s timeout) or returns an error, the dashboard shows a friendly message and a **Retry** button, which re-fetches without a full page reload. If only `/integrations` fails, services still render with a notice.

## Project structure

```
app/                 Root layout, page and global styles (design tokens live in globals.css)
components/
  layout/            Shell, header, sidebar, mobile nav, notifications
  dashboard/         Summary cards, system health chart, deployments
  incidents/         Incident cards, list with filters, detail drawer
  services/          Service health list; loading, error and empty states
  activity/          Activity timeline
  ui/                Shared primitives (Panel, Badge, StatusDot, AnimatedNumber)
lib/
  api.ts             Typed API client (server-only): /health, /services, /integrations; planned endpoints
  services.ts        Service summaries and integration grouping
  demo-data.ts       Demo data for sections without backend endpoints yet
  status.ts          Status colours and labels
  search.ts          Header search matching
  motion.ts          Shared animation presets
  format.ts          Time and duration formatting
types/index.ts       API response types (Service, Integration) and demo data types
```

## Accessibility and motion

- All animations respect the OS "reduce motion" setting (`MotionConfig reducedMotion="user"`).
- Status is always conveyed with text and icons, not colour alone.
- Loading placeholders are announced as status regions; API errors use `role="alert"`.
- Drawers and menus close with <kbd>Esc</kbd>; a skip link jumps to the main content.
