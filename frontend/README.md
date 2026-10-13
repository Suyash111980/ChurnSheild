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
| `/dashboard` | Dashboard metrics availability and API status | Protected |
| `/learners` | Authenticated, paginated learner records | Protected |
| `/learners/:learnerId` | Learner detail by database UUID; requires a detail API route | Protected |
| `/analytics` | Existing analytics page | Protected |
| `/early-warning` | Existing early-warning workspace | Protected |
| `/root-cause` | Existing root-cause workspace | Protected |
| `/recommendations` | Existing recommendations workspace | Protected |
| `/course-insights` | Existing course insights | Protected |
| `/reports` | Existing reports workspace | Protected |
| `/settings` | Account and application settings | Protected |
| `/account-status` | Approval status | Authenticated |

## Current backend integration contract

- `GET /api/v1/learners?limit=<1..100>&offset=<n>` is implemented. It returns a `data` array and page metadata. The current contract does not provide a total count, search/filter/sort parameters, risk predictions, activity/performance signals, or `student_name`.
- The learner page uses backend `limit`/`offset` pagination. Search, module/presentation filters, and sorting operate on the currently fetched page only.
- When the backend includes `student_name` in a learner record, it is display-only. Otherwise the UI uses `Learner <id_student>` and keeps the database UUID, learner ID, module, and presentation distinct.
- `GET /api/v1/learners/{id}` is not currently implemented. The profile route reports this dependency and uses the database UUID as its route identifier; it does not substitute fabricated profile information.
- A dashboard summary/statistics endpoint is not currently implemented. The dashboard therefore shows no fabricated totals, risk distributions, retention rates, or trends.
- Phase 1 and Phase 2 screens outside the API-backed learner and dashboard work remain in place. Backend, database, and ML integration changes are not part of this frontend branch.

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

Install dependencies, start the backend and Supabase configuration, then run `npm run dev` from `frontend/`. Phase 3/4 displays live learner fields only where the current backend contract provides them; risk predictions, learner detail profiles, and dashboard aggregates remain dependent on backend endpoints and fields that are not yet implemented.
