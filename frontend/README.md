# ChurnShield Frontend

The ChurnShield frontend is a responsive React dashboard for learner retention. It uses the existing Supabase authentication flow and the authenticated FastAPI API client. Dashboard analytics are shown only when an implemented backend response supports them; unavailable metrics are labeled instead of filled with mock values.

## Technologies

- React with functional components and hooks
- Vite
- Tailwind CSS 4 and the existing responsive CSS design system
- React Router
- Lucide React
- Supabase Auth for the existing sign-in/session flow

## Prerequisites

- Node.js 20.19+ or 22.12+
- npm
- The ChurnShield FastAPI service and configured Supabase project for authenticated API access

## Install and run

Run these commands from the frontend directory:

```powershell
cd "D:\AI INNOVATION\ChurnSheild\frontend"
npm install
npm run dev
```

The frontend reads configuration from Vite environment variables. Copy `.env.example` to `.env.local` and set the API base URL, Supabase project URL, and Supabase publishable/anon key. Do not put service-role keys or private credentials in frontend environment variables.

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_SUPABASE_URL=
VITE_SUPABASE_PUBLISHABLE_KEY=
```

Create and preview a production build from the same directory:

```powershell
npm run build
npm run preview
```

## Authentication

Login and signup continue to use the existing Supabase Auth integration. The API client attaches the current Supabase access token and attempts the existing session refresh flow after an unauthorized response. Protected dashboard routes require an authenticated session and an approved account. This frontend does not implement a parallel demo-auth system or bypass backend authorization.

## Routes

| Route | Purpose | Access |
| --- | --- | --- |
| `/login` | Sign in with the configured Supabase project | Public/guest |
| `/signup` | Create an account through the existing Supabase flow | Public/guest |
| `/dashboard` | Selected dataset summary and persisted risk distribution | Approved account |
| `/datasets` | Preview, validate, upload, and reprocess a dataset | Approved Admin or Master Admin with active workspace |
| `/learners` | Dataset-scoped learner records with backend pagination | Approved account |
| `/learners/:learnerId` | Dataset-scoped profile by database UUID | Approved account |
| `/analytics` | Dataset coverage, descriptive counts, and prediction coverage | Approved account |
| `/early-warning` | Paginated saved predictions and available persisted evidence | Approved account |
| `/root-cause` | Saved learner prediction and persisted explanations, when present | Approved account |
| `/recommendations` | Persisted recommendations and permitted status changes | Approved account; status changes are role-limited |
| `/course-insights` | Dataset coverage; course-specific metrics shown unavailable | Approved account |
| `/reports` | Dataset-scoped learner CSV export | Approved account |
| `/settings` | Dataset status, session controls, and browser-local preferences | Approved account |
| `/admin/users` | Admin approval requests | Master Admin |
| `/master-admin` | Platform account and workspace metadata | Master Admin |
| `/master-admin/oulad` | Manual upload of the prepared OULAD cohort through the existing dataset flow | Master Admin |
| `/account-status` | Approval status | Authenticated |

## Current backend integration contract

- Dataset operations use `POST /api/v1/datasets/preview`, `POST /api/v1/datasets/upload`, `GET /api/v1/datasets`, `GET /api/v1/datasets/{id}`, and `POST /api/v1/datasets/{id}/reprocess`. The UI previews validation before upload and displays the backend processing state. The API processes uploads synchronously; it does not provide background progress updates.
- `GET /api/v1/dashboard/summary?dataset_id=...` returns real learner/course counts, prediction coverage, and nullable risk distribution. Missing prediction data remains unavailable; no retention-rate or historical-outcome chart is inferred.
- Learner list and profile APIs are `GET /api/v1/learners?dataset_id=...&limit=...&offset=...` and `GET /api/v1/learners/{database_uuid}?dataset_id=...`. The list API supports exact learner-ID, module, presentation, and risk-category filters. The current page's free-text search, available filter choices, and sorting operate on the fetched page; results are not yet searched or sorted server-side by arbitrary text.
- `GET /api/v1/predictions`, `GET /api/v1/predictions/{id}`, `GET /api/v1/predictions/{id}/explanations`, and `GET /api/v1/learners/{id}/predictions` are read-only. Prediction creation is performed by supported dataset processing, not a public `POST /predictions` API.
- `GET /api/v1/early-warning` returns saved predictions and persisted evidence. `GET /api/v1/recommendations` returns persisted recommendations; `PATCH /api/v1/recommendations/{id}` changes status for authorized roles. Recommendation generation and explanation persistence are not implemented by the upload flow.
- `GET /api/v1/reports/learners.csv?dataset_id=...` is the available export. Risk-analysis and recommendation exports, a generic `/reports/export`, and Excel export are not implemented.
- `GET /api/v1/analytics/model-evaluation` and Master Admin overview/OULAD endpoints are Master Admin-only. Model training/evaluation diagnostics are not displayed in the Master Admin UI. Course-level breakdowns, weekly trends, workspace-specific model evaluation, and profile-update APIs are unavailable.
- Admin approvals are backed by `/api/v1/admin/pending-users` and `/api/v1/admin/users/{id}/approval`. Settings preferences currently live in component state and are not persisted; profile editing is not available.
- Optional `student_name` is display-only. Otherwise the UI uses the learner identifier and keeps database UUID, source learner ID, module, and presentation distinct.

## Source layout

```text
src/
  components/common/   Shared loading, error, and empty states
  components/layout/   Sidebar, topbar, page header, and app shell
  components/learners/ Learner filters, table, and risk badge
  context/             Existing Supabase authentication state
  hooks/               Dashboard and learner data hooks
  pages/               Auth, dashboard, learner, and workspace pages
  services/            Centralized API and feature service modules
  App.jsx               Routes and protected-route guards
  main.jsx              React and browser-router entry point
```

Install dependencies, start the backend and configure Supabase, then run `npm run dev` from `frontend/`. Run `npm test` for the current Node test suite and `npm run build` for the Vite production build. End-to-end Supabase behavior requires a configured non-production project and deployed reviewed migrations; this README does not imply that live connectivity or database writes have been verified.

## Current interaction and chart integrations

- The collapsible desktop sidebar and mobile navigation drawer use the existing routes and account-role visibility. The topbar profile menu reads the authenticated Supabase user and `/auth/status` profile; its logout action uses the existing Supabase logout flow.
- The notification drawer is UI-only and intentionally shows an empty state. There is no notification API or event stream, so notifications, unread counts, and mark-as-read actions are not simulated.
- Global search matches application sections locally. Learner search calls the existing learner API, fetches its first 100 records, and searches those results client-side; there is no server-side search endpoint.
- Dashboard and learner views use the selected dataset and persisted API responses. Historical outcomes and engagement timelines remain unavailable when the API does not provide those fields; no example values are presented as live results.
- Root Cause Analysis and Early Warning Center use saved predictions and explanations when returned by the backend. The UI keeps model contributions distinct from causal evidence.
