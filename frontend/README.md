# ChurnShield Frontend

The ChurnShield frontend is a responsive learner-retention analytics demo. Phase 1 runs entirely in the browser and uses illustrative learner and dashboard values. It does not connect to the backend, database, machine-learning pipeline, Firebase, or an external identity provider.

## Technologies

- React 19 with functional components and hooks
- Vite 8
- Tailwind CSS 4 (Vite plugin) with project-specific responsive styles
- React Router for client-side navigation
- Lucide React icons

## Prerequisites

- Node.js 20.19+ or 22.12+
- npm

## Install and run

From the repository's `frontend` directory:

```powershell
cd "D:\AI INNOVATION\ChurnSheild\frontend"
npm install
npm run dev
```

To create and preview the production build:

```powershell
npm run build
npm run preview
```

## Demo authentication

Open `/signup` to create a demo account using a name, email, and password of your choice. Passwords must be at least 8 characters, and confirmation and the demo-terms checkbox are required. The account is created locally in this browser; a SHA-256 password hash is stored in local storage, never the password. The active session profile is kept in session storage. The login page validates the email and credentials, and its “Remember me” option keeps only the session profile in local storage. Logging out clears the session and returns to `/login`.

This is a browser-only demonstration, not production authentication. Do not use a real password or sensitive personal information. Browser storage is not a secure credential store, and clearing site data removes demo accounts. There is no password reset in Phase 1.

## Routes

| Route | Purpose | Access |
| --- | --- | --- |
| `/login` | Demo account sign-in | Public |
| `/signup` | Create a browser-local demo account | Public |
| `/dashboard` | Illustrative retention metrics and trends | Protected |
| `/learners` | Searchable, filterable sample learner table | Protected |
| `/analytics` | Sample course and engagement analytics | Protected |
| `/settings` | Dataset, safeguards, notifications, and account | Protected |
| `/early-warning` | Risk review queue | Protected |
| `/root-cause` | Illustrative risk explanation | Protected |
| `/recommendations` | Human-reviewed action queue | Protected |
| `/course-insights` | Course and cohort insights | Protected |
| `/reports` | Exportable demo summaries | Protected |

Unauthenticated dashboard visits redirect to `/login`; authenticated visits to login or signup redirect to `/dashboard`. Unknown routes show a not-found page.

## Source layout

```text
src/
  components/layout/   Shared sidebar, topbar, page header, and app shell
  context/             Browser-only demo authentication state
  pages/               Login, signup, dashboard, learners, analytics, settings
  index.css            Tailwind entry and responsive design system
  App.jsx               Route definitions and route guards
  main.jsx              React and browser-router entry point
```

The learner and dashboard values are fictional interface fixtures and are labeled as illustrative. Phase 1 does not include backend integration.

