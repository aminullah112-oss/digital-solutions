# Kite Algo: Zerodha Kite Connect login + dashboard

A small starter app: **React + Vite** frontend, **Python FastAPI** backend.

- You enter your **API Key**, **API Secret** and **Request Token** on a login page.
- The backend uses the official `kiteconnect` SDK to create the **access token** and saves it on disk. **The browser never sees the access token.**
- The saved token is reused, so restarting the backend or editing code does not log you out.
- A dark-mode dashboard with tabs. The first tab, **User**, shows your name, user ID, products and exchanges.

```
kite-algo/
├── backend/            FastAPI + kiteconnect
│   ├── main.py         API endpoints
│   ├── token_store.py  saves/loads the session file
│   └── tests/          pytest tests (no real credentials needed)
└── frontend/           React + Vite
    └── src/
        ├── styles/theme.css   colors, fonts, radius: edit this to restyle
        ├── tabs/index.js      list of dashboard tabs: add yours here
        ├── tabs/UserTab.jsx   the User tab
        └── pages/             Login and Dashboard pages
```

## 1. One-time Kite Connect setup

1. Create an app at <https://developers.kite.trade/apps>.
2. Set its **Redirect URL** to exactly:
   ```
   http://localhost:5173/login
   ```
3. Copy the app's **API Key** and **API Secret**.

The redirect URL is what makes the login smooth: after you sign in on Zerodha, Kite sends you back to this app and the **Request Token is filled in for you**.

## 2. Install and run

You need **Python 3.9+** and **Node.js 18+**. Use two terminals.

**Terminal 1: backend**

Windows (PowerShell):
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

macOS / Linux:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and retry.

**Terminal 2: frontend**
```bash
cd frontend
npm install
npm run dev
```

Open **<http://localhost:5173>**.

## 3. Log in

1. Type your **API Key**. An **Open Kite login** link appears under Request Token.
2. Click it, sign in to Zerodha (user ID, password, TOTP). You land back on this app with the Request Token already filled in.
3. Type your **API Secret** and press **Login**.

You are taken to the dashboard.

**Request tokens are single-use and expire within minutes.** If login fails with "Token is invalid or has expired", get a fresh one with the link and try again.

## How "stay logged in" works

The backend writes `api_key` and `access_token` to `backend/.data/session.json` (git-ignored, owner-only permissions on macOS/Linux). On every page load the frontend asks the backend `GET /api/auth/status`, which checks the saved token with Kite. Because the file survives `uvicorn --reload`, code changes don't log you out.

**Kite access tokens expire every day (around 6 AM IST).** When that happens the backend deletes the dead token and the app sends you to the login page. That is a Kite rule; the app can't avoid it.

The **API Secret is never saved.** It is only used once, in memory, to create the token.

## API

| Method | Path | What it does |
|---|---|---|
| POST | `/api/auth/login` | `{api_key, api_secret, request_token}` → creates and saves the token. Returns user id/name only. |
| GET | `/api/auth/status` | Is the saved token still valid? |
| POST | `/api/auth/logout` | Invalidates the token at Kite and deletes the saved file. |
| GET | `/api/profile` | Returns `user_name`, `user_id`, `products`, `exchanges`. |
| GET | `/api/health` | Liveness check. |

Interactive docs: <http://127.0.0.1:8000/docs>.

## Customize the look

- **Colors, fonts, roundness, page width:** edit the variables in `frontend/src/styles/theme.css`. Every component reads from them. For example, change `--accent` and `--accent-soft` for a new brand color.
- **Layout and components:** `frontend/src/styles/app.css`.
- **Add a tab:** create `frontend/src/tabs/HoldingsTab.jsx`, then add one line to `frontend/src/tabs/index.js`:
  ```js
  { id: "holdings", label: "Holdings", component: HoldingsTab },
  ```
  Add a matching endpoint in `backend/main.py` that uses `_authed_kite()` (it returns a ready-to-use `KiteConnect` client) and call it from the tab with a function in `frontend/src/api.js`.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

The tests use a fake Kite client. They check that the token and secret never appear in a response, that the session survives a restart, and that expired tokens are cleared.

## Security notes (read these)

- **Run the backend on `127.0.0.1` only**, as shown above. There is no app-level password, so anyone who can reach port 8000 can use your saved Kite session. Don't expose it to a network, a tunnel, or `0.0.0.0`.
- This stores the access token **unencrypted** in `backend/.data/session.json`. That is fine for local development on your own machine. Before using this anywhere shared or hosted, move it to an encrypted store or a secrets manager and add real authentication.
- Never commit `backend/.data/` or any `.env` file. The included `.gitignore` already excludes them.
- The API Secret passes through the browser form once on its way to the backend (over `localhost`). Keep it out of screenshots and chat messages.
- Never paste an access token or API secret into an AI chat or an issue.
- This app only reads your profile. It does not place orders. If you add order placement later, add confirmation steps and test with small quantities first; the Kite API has no sandbox.
