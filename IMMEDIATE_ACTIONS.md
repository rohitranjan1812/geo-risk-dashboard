# Immediate Action Items
## Critical Security Fixes Required Before Production

**Based on**: PR #2 Testing Outcome Analysis
**Priority**: CRITICAL - Must be addressed before any production deployment
**See**: [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) for full details

---

## 🚨 CRITICAL - Fix Immediately (Days, Not Weeks)

### 1. SQL Injection Vulnerabilities

**Risk**: Attackers can execute arbitrary SQL queries, read/modify/delete data

**Files to Fix**:
- `georisk/backend/app/api/routes_synthetic.py:225`
- `georisk/backend/app/api/routes_cat.py:146`

**Current Vulnerable Code Pattern**:
```python
# ❌ VULNERABLE - DO NOT USE
query = f"SELECT * FROM table WHERE {where} LIMIT {page_size} OFFSET {offset}"
```

**Required Fix**:
```python
# ✅ SAFE - Use parameterized queries
query = "SELECT * FROM table WHERE column = ? LIMIT ? OFFSET ?"
params = [user_value, page_size, offset]
result = conn.execute(query, params)
```

**Action Steps**:
1. Audit all files for f-string SQL queries with user input
2. Create query builder utility for safe WHERE clause construction
3. Replace ALL vulnerable queries with parameterized versions
4. Add SQL injection tests to prevent regression
5. Code review with security focus

**Estimated Time**: 2-3 days

---

### 2. No Authentication on ANY Endpoint

**Risk**: Anyone can access, modify, or delete all data without credentials

**Current State**: Zero authentication on 50+ endpoints

**Required Fix**:
1. **Choose auth strategy**: JWT recommended for API-first architecture
2. **Implement user management**:
   - User model (id, username, password_hash, role)
   - Registration/login endpoints
   - Password hashing (bcrypt or argon2)
3. **Add authentication middleware**:
   - Verify JWT on every request
   - Return 401 for invalid/missing tokens
4. **Implement authorization**:
   - Define roles (admin, analyst, viewer)
   - Protect endpoints with role checks
5. **Update frontend**:
   - Login UI
   - Store JWT securely
   - Add auth headers to all requests

**Recommended Library**: FastAPI-Users (https://fastapi-users.github.io/fastapi-users/)

**Estimated Time**: 4-5 days

---

### 3. File Upload Security

**Risk**: DoS attacks via large files, potential code execution

**Required Fixes**:
1. **Add file size limits**:
   ```python
   app.add_middleware(
       ContentSizeLimitMiddleware,
       max_content_size=10_000_000  # 10MB
   )
   ```

2. **Validate file types**:
   ```python
   ALLOWED_TYPES = {".csv", ".json", ".geojson"}
   if file_ext not in ALLOWED_TYPES:
       raise HTTPException(400, "Invalid file type")
   ```

3. **Fix path traversal in `load_geojson()`**:
   ```python
   # ❌ VULNERABLE
   def load_geojson(filename):
       with open(f"data/{filename}") as f:  # Can use "../../../etc/passwd"
           return json.load(f)

   # ✅ SAFE
   def load_geojson(filename):
       safe_path = os.path.abspath(os.path.join("data", filename))
       if not safe_path.startswith(os.path.abspath("data")):
           raise ValueError("Invalid path")
       with open(safe_path) as f:
           return json.load(f)
   ```

**Estimated Time**: 1-2 days

---

## ⚠️ HIGH PRIORITY - Fix This Week

### 4. Disable Debug Mode for Production

**File**: `georisk/backend/app/config.py`

**Current Issue**: Debug mode enabled by default exposes:
- Full stack traces to users
- Interactive debugger (security risk)
- Detailed error messages

**Fix**:
```python
# Use environment variable
import os
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Or use Pydantic settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    debug: bool = False  # Default to False

    class Config:
        env_file = ".env"
```

**Estimated Time**: 30 minutes

---

### 5. Fix CORS Configuration

**File**: `georisk/backend/app/main.py`

**Current Issue**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Too permissive
    allow_methods=["*"],  # Too permissive
)
```

**Fix**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://app.yourdomain.com",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)
```

**For Local Development**:
```python
if settings.debug:
    allow_origins = ["http://localhost:3000", "http://localhost:5173"]
else:
    allow_origins = ["https://yourdomain.com"]
```

**Estimated Time**: 15 minutes

---

### 6. Add Rate Limiting

**Risk**: API abuse, DoS attacks, resource exhaustion

**Install**:
```bash
pip install slowapi
```

**Implement**:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# On expensive endpoints
@app.post("/api/scenarios/what-if")
@limiter.limit("10/minute")  # Max 10 requests per minute
async def what_if_scenario(request: Request, ...):
    ...
```

**Estimated Time**: 2-3 hours

---

### 7. CSV Formula Injection Prevention

**Risk**: Excel formulas in exported CSVs can execute arbitrary code

**Fix**:
```python
def sanitize_csv_cell(value: str) -> str:
    """Prevent CSV formula injection."""
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + value  # Prefix with single quote
    return value

# Apply to all CSV exports
def export_to_csv(data):
    sanitized = [
        {k: sanitize_csv_cell(v) for k, v in row.items()}
        for row in data
    ]
    return pd.DataFrame(sanitized).to_csv()
```

**Estimated Time**: 1-2 hours

---

## 📋 Quick Implementation Checklist

Use this checklist to track immediate security fixes:

### SQL Injection (P0)
- [ ] Audit all DuckDB/SQLite queries
- [ ] Identify f-string queries with user input
- [ ] Create parameterized query utility
- [ ] Replace vulnerable queries
- [ ] Add SQL injection tests
- [ ] Security code review

### Authentication (P0)
- [ ] Install FastAPI-Users or equivalent
- [ ] Create user model and database
- [ ] Implement registration/login
- [ ] Add JWT generation/validation
- [ ] Protect all endpoints
- [ ] Update frontend with auth UI
- [ ] Test auth flows

### File Security (P0)
- [ ] Add file size limits
- [ ] Validate file types
- [ ] Fix path traversal in load_geojson
- [ ] Sanitize file paths everywhere
- [ ] Test with malicious inputs

### Production Config (P1)
- [ ] Disable debug mode
- [ ] Configure CORS properly
- [ ] Add rate limiting
- [ ] Sanitize CSV exports

---

## Testing Your Fixes

### SQL Injection Test
```python
# Try to break it
malicious_where = "1=1; DROP TABLE properties--"
response = client.get(f"/api/synthetic?where={malicious_where}")
# Should return error, not execute DROP TABLE
```

### Auth Test
```python
# Without token
response = client.get("/api/properties/")
assert response.status_code == 401

# With invalid token
response = client.get(
    "/api/properties/",
    headers={"Authorization": "Bearer fake_token"}
)
assert response.status_code == 401

# With valid token
response = client.get(
    "/api/properties/",
    headers={"Authorization": f"Bearer {valid_token}"}
)
assert response.status_code == 200
```

### Path Traversal Test
```python
# Try to access /etc/passwd
malicious_path = "../../../etc/passwd"
response = client.get(f"/api/data/geojson?file={malicious_path}")
# Should return error, not file contents
```

---

## Before You Deploy

### Pre-Production Checklist
- [ ] All critical vulnerabilities fixed
- [ ] Authentication implemented and tested
- [ ] SQL injection tests passing
- [ ] Debug mode disabled
- [ ] CORS configured for production domain
- [ ] Rate limiting active
- [ ] File upload limits in place
- [ ] Error messages don't expose internals
- [ ] Secrets stored in environment variables (not code)
- [ ] Security audit performed
- [ ] Penetration testing completed

### Don't Deploy Until:
1. ✅ SQL injection vulnerabilities fixed
2. ✅ Authentication implemented
3. ✅ File security implemented
4. ✅ Production config applied
5. ✅ Security tests passing
6. ✅ Third-party security audit (recommended)

---

## Getting Help

### Resources
- **OWASP Top 10**: https://owasp.org/Top10/
- **FastAPI Security**: https://fastapi.tiangolo.com/tutorial/security/
- **SQL Injection Prevention**: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html

### Questions?
Refer to the full [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) for:
- Detailed implementation steps
- Complete roadmap (4 phases)
- Risk management strategy
- Success metrics

---

## Summary

**What PR #2 Gave Us**:
- ✅ 179 comprehensive tests
- ✅ Bug fix for NumPy compatibility
- ✅ Identified security gaps

**What We Must Do Next**:
- 🚨 Fix SQL injection (2-3 days)
- 🚨 Implement authentication (4-5 days)
- 🚨 Secure file handling (1-2 days)
- ⚠️ Production hardening (1 day)

**Total Time to Production-Ready**: ~2 weeks for critical fixes

---

*Last Updated: April 6, 2026*
*See DEVELOPMENT_PLAN.md for complete details*
