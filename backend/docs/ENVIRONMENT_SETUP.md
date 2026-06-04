# Environment Setup Guide

## Quick Start (Development Mode)

### 1. Copy Environment Template

```bash
cd backend
cp .env.example .env
```

### 2. Configure Minimum Required Settings

Edit `backend/.env`:

```env
# Enable development mode
ENVIRONMENT=development

# Leave empty for auth bypass (dev@localhost user auto-created)
SECRET_KEY=

# Required: Set your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional: Set other defaults
DATABASE_URL=sqlite+aiosqlite:///./dev.db
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-sonnet-4-5
```

### 3. Start the Server

```bash
# Install dependencies (first time only)
uv sync

# Start backend
uv run uvicorn api.main:app --reload --port 8000
```

### 4. Test Without Authentication

```bash
# No Authorization header needed in dev mode!
curl http://localhost:8000/api/v1/projects
# Returns: []
```

---

## Development Mode Features

### Authentication Bypass

When both conditions are true:
- `ENVIRONMENT=development`
- `SECRET_KEY=` (empty string)

The system automatically:
1. Creates `dev@localhost` superuser on first request
2. Skips JWT token validation
3. All API requests work without `Authorization` header
4. Full access to all endpoints (superuser role)

**Example:**
```http
GET http://localhost:8000/api/v1/projects
# No auth header needed - works immediately!
```

### LLM API Key Optional

In development mode, the server starts even without LLM API keys. This allows testing non-LLM endpoints (projects, use-cases, etc.) without provider credentials.

**Note:** Endpoints that use LLM will fail at runtime if no API key is set.

---

## Production Mode

### Required Settings

```env
# Production mode
ENVIRONMENT=production

# REQUIRED: Secure JWT secret (min 32 characters)
SECRET_KEY=your-super-secure-random-key-min-32-chars

# REQUIRED: API secret key
API_SECRET_KEY=your-api-secret-key

# REQUIRED: Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-production-key

# Recommended: PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/rpa_intelligence

# Recommended: Production Redis
REDIS_URL=redis://production-redis:6379/0
```

### Authentication Flow (Production)

1. **Register a user:**
```http
POST http://localhost:8000/api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure-password"
}
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

2. **Use token in requests:**
```http
GET http://localhost:8000/api/v1/projects
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Environment Variables Reference

### Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | `development` or `production` |
| `DATABASE_URL` | No | SQLite | Database connection string |
| `SECRET_KEY` | Production | `""` | JWT signing key (empty = dev auth bypass) |
| `API_SECRET_KEY` | Production | `""` | X-API-Key header value (empty = disabled) |

### LLM Provider

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEFAULT_LLM_PROVIDER` | No | `anthropic` | `anthropic`, `openai`, `watsonx`, `ollama` |
| `DEFAULT_LLM_MODEL` | No | `claude-sonnet-4-5` | Model name for chosen provider |
| `ANTHROPIC_API_KEY` | If provider=anthropic | `""` | Anthropic API key |
| `OPENAI_API_KEY` | If provider=openai | `""` | OpenAI API key |
| `LLM_MAX_RETRIES` | No | `3` | Max retry attempts on rate limit |
| `LLM_RETRY_BASE_DELAY` | No | `1.0` | Base delay for exponential backoff (seconds) |

### Optional Services

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis for session storage |
| `FRONTEND_URL` | No | `http://localhost:3000` | Frontend URL for CORS |
| `OUTPUT_DIR` | No | `data/outputs` | Generated files directory |
| `TEMP_DIR` | No | `data/temp` | Temporary files directory |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Feature Flags

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `USE_LANGGRAPH_COMPLEXITY_AGENT` | No | `false` | Use v2 LangGraph agent for Stage 2 |

---

## LLM Provider Configuration

### Anthropic (Default)

```env
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Recommended models:**
- `claude-sonnet-4-6` — Latest, best balance
- `claude-sonnet-4-5` — Stable, proven
- `claude-haiku-4-5` — Fast, cheaper
- `claude-opus-4-8` — Highest quality

### OpenAI

```env
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-your-key-here
```

**Recommended models:**
- `gpt-4o` — Latest multimodal
- `gpt-4-turbo` — Fast, cost-effective

### Watsonx (IBM)

```env
DEFAULT_LLM_PROVIDER=watsonx
DEFAULT_LLM_MODEL=ibm/granite-13b-chat-v2
WATSONX_API_KEY=your-key
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_PROJECT_ID=your-project-id
```

### Ollama (Local)

```env
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_LLM_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
```

**Note:** Requires Ollama server running locally.

---

## Database Configuration

### SQLite (Development)

```env
DATABASE_URL=sqlite+aiosqlite:///./dev.db
```

**Pros:** Simple, no setup required  
**Cons:** Single-file, not for production

### PostgreSQL (Production)

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/rpa_intelligence
```

**Setup:**
```bash
# Create database
createdb rpa_intelligence

# Run migrations
uv run alembic upgrade head
```

---

## Troubleshooting

### "ANTHROPIC_API_KEY is required" Error

**Problem:** Server won't start without API key in production mode.

**Solution (Development):**
```env
ENVIRONMENT=development  # Skip API key validation
```

**Solution (Production):**
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### "Not authenticated" (401 Error)

**Problem:** API requests return 401 Unauthorized.

**Solution (Development):**
```env
ENVIRONMENT=development
SECRET_KEY=  # Must be empty string, not commented out
```

**Solution (Production):**
1. Register user: `POST /api/v1/auth/register`
2. Get token from response
3. Add header: `Authorization: Bearer <token>`

### Server Starts But LLM Calls Fail

**Problem:** Non-LLM endpoints work, but Stage 2 scoring fails.

**Cause:** No API key set for LLM provider.

**Solution:**
```env
# Set the key for your chosen provider
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Database Locked Error (SQLite)

**Problem:** Multiple processes accessing SQLite.

**Solution:** Use PostgreSQL for multi-process deployments:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/db
```

### LangGraph Agent Not Working

**Problem:** v2 agent features not available.

**Solution:** Enable the feature flag:
```env
USE_LANGGRAPH_COMPLEXITY_AGENT=true
```

---

## Security Best Practices

### Development

✅ **DO:**
- Use empty `SECRET_KEY` for auth bypass
- Use local SQLite database
- Use `.env` file (not committed to git)
- Test with `ENVIRONMENT=development`

❌ **DON'T:**
- Commit `.env` file to git
- Use production API keys in development
- Share your `.env` file

### Production

✅ **DO:**
- Set `ENVIRONMENT=production`
- Use strong `SECRET_KEY` (min 32 random chars)
- Set `API_SECRET_KEY` for additional security
- Use PostgreSQL, not SQLite
- Enable HTTPS (reverse proxy)
- Rotate API keys regularly
- Use environment-specific `.env` files

❌ **DON'T:**
- Leave `SECRET_KEY` empty
- Use default/weak secrets
- Expose `.env` file in deployments
- Skip API key validation

---

## Example Configurations

### Minimal Development Setup

```env
ENVIRONMENT=development
SECRET_KEY=
ANTHROPIC_API_KEY=sk-ant-your-key
```

### Full Development Setup

```env
ENVIRONMENT=development
DATABASE_URL=sqlite+aiosqlite:///./dev.db
SECRET_KEY=
API_SECRET_KEY=
ANTHROPIC_API_KEY=sk-ant-your-key
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-sonnet-4-5
LLM_MAX_RETRIES=3
REDIS_URL=redis://localhost:6379/0
FRONTEND_URL=http://localhost:3000
LOG_LEVEL=DEBUG
USE_LANGGRAPH_COMPLEXITY_AGENT=false
```

### Production Setup

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://user:pass@prod-db:5432/rpa
SECRET_KEY=your-super-secure-random-key-min-32-characters-long
API_SECRET_KEY=your-api-secret-key-for-additional-security
ANTHROPIC_API_KEY=sk-ant-production-key
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-sonnet-4-6
LLM_MAX_RETRIES=3
LLM_RETRY_BASE_DELAY=1.0
REDIS_URL=redis://prod-redis:6379/0
FRONTEND_URL=https://app.yourcompany.com
LOG_LEVEL=INFO
LOG_FORMAT=json
USE_LANGGRAPH_COMPLEXITY_AGENT=true
```

---

## Testing Your Configuration

### 1. Verify Settings Load

```bash
uv run python -c "from config import get_settings; print(get_settings().environment)"
# Should print: development
```

### 2. Test Auth Bypass (Dev Mode)

```bash
curl http://localhost:8000/api/v1/projects
# Should return: [] (not 401)
```

### 3. Test LLM Connection

```bash
# Create a test use-case and run Stage 2
# (Requires frontend or direct API calls)
```

### 4. Check Database

```bash
uv run alembic current
# Should show current migration version
```

---

## Next Steps

1. ✅ Copy `.env.example` to `.env`
2. ✅ Configure minimum settings (ENVIRONMENT, SECRET_KEY, ANTHROPIC_API_KEY)
3. ✅ Start server: `uv run uvicorn api.main:app --reload`
4. ✅ Test endpoint: `curl http://localhost:8000/api/v1/projects`
5. ✅ Start frontend: `cd ../frontend && npm run dev`
6. ✅ Access app: http://localhost:3000

---

## Support

- **Configuration Issues:** Check this guide and `.env.example` comments
- **Auth Issues:** See [Auth Bypass](#authentication-bypass) section
- **LLM Issues:** Verify API key and provider settings
- **Database Issues:** Check `DATABASE_URL` and run migrations

**Need help?** Check the main CLAUDE.md for project-specific guidance.
