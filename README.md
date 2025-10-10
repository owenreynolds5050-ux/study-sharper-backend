# Study Sharper Backend

FastAPI backend for Study Sharper application.

## 🚀 Deployment to Render

### Quick Deploy
1. Push this repository to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Select the `Study_Sharper_Backend` directory (use root directory selector)
6. Render will auto-detect the `render.yaml` configuration

### Manual Configuration (if auto-detect doesn't work)
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Python Version:** 3.11.0

### Environment Variables
Set these in Render Dashboard → Your Service → Environment:

| Variable | Description | Where to Find |
|----------|-------------|---------------|
| `SUPABASE_URL` | Your Supabase project URL | Supabase Dashboard → Settings → API → URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (NOT anon key) | Supabase Dashboard → Settings → API → service_role key |
| `OPENROUTER_API_KEY` | OpenRouter API key for AI chat | [OpenRouter Dashboard](https://openrouter.ai/keys) |
| `ALLOWED_ORIGINS` | Comma-separated allowed domains | Your Vercel URLs, e.g., `https://your-app.vercel.app,https://your-app-git-main.vercel.app` |

### After Deployment
1. Copy your Render service URL (e.g., `https://study-sharper-backend.onrender.com`)
2. Add it as `BACKEND_API_URL` in Vercel environment variables
3. Update `ALLOWED_ORIGINS` on Render to include your Vercel domain

## 🧪 Local Development

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your environment variables in `.env`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

5. API will be available at: `http://localhost:8000`
   - API docs: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/`

## 📁 Project Structure

```
app/
├── api/           # API route handlers
│   ├── chat.py    # AI chat endpoints
│   ├── notes.py   # Notes and folders CRUD
│   └── upload.py  # File upload handling
├── core/          # Core configuration
│   ├── auth.py    # Authentication middleware
│   └── config.py  # Environment configuration
├── services/      # External service integrations
│   ├── open_router.py      # OpenRouter AI integration
│   └── text_extraction.py  # PDF/DOCX text extraction
└── main.py        # FastAPI application entry point
```

## 🔒 Security Notes

- Backend uses **service role key** to bypass RLS for admin operations
- User JWT tokens are validated via `get_current_user()` dependency
- All database queries are filtered by `user_id` for data isolation
- CORS is restricted to configured origins only
