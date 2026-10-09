# CloudOps AI — Frontend

Dashboard for CloudOps AI, built with Next.js (App Router), TypeScript, Tailwind CSS and Motion for React (`motion`, imported from `motion/react`).

> The dashboard currently renders **demo data** from `lib/demo-data.ts`. It will switch to the FastAPI backend as endpoints become available.

## Requirements

- Node.js 20.9+ (developed on Node 22)

## Getting started

From the `frontend/` directory:

```bash
npm install
npm run dev
```

Open http://localhost:3000.

## Scripts

| Command         | Purpose                         |
| --------------- | ------------------------------- |
| `npm run dev`   | Start the dev server            |
| `npm run lint`  | Run ESLint                      |
| `npm run build` | Production build + type check   |
| `npm start`     | Serve the production build      |

## Configuration

| Variable                   | Default                 | Description                    |
| -------------------------- | ----------------------- | ------------------------------ |
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Base URL of the CloudOps API   |

## Project structure

```
app/                 Root layout, page and global styles (design tokens live in globals.css)
components/
  layout/            Shell, header, sidebar, mobile nav, notifications
  dashboard/         Summary cards, system health chart, deployments
  incidents/         Incident cards, list with filters, detail drawer
  services/          Service health list
  activity/          Activity timeline
  ui/                Shared primitives (Panel, Badge, StatusDot, Sparkline, AnimatedNumber)
lib/
  api.ts             Typed API client (GET /health now; incidents, services, deployments, telemetry planned)
  demo-data.ts       Static demo data — to be replaced by API responses
  status.ts          Status colours and labels
  motion.ts          Shared animation presets
  format.ts          Time and duration formatting
types/index.ts       Domain types shared by the API client and components
```

## Connecting to the backend

`app/page.tsx` loads data through `getDashboardData()` in `lib/api.ts`. To use live data, replace its body with calls to `getIncidents()`, `getServices()`, `getDeployments()` and `getTelemetry()` once those endpoints exist. Components consume the types in `types/index.ts` and need no changes.

## Accessibility and motion

- All animations respect the OS "reduce motion" setting (`MotionConfig reducedMotion="user"`).
- Status is always conveyed with text and icons, not colour alone.
- Drawers and menus close with <kbd>Esc</kbd>; a skip link jumps to the main content.
