# GeoRisk Development Plan
## Based on PR #2 Testing Outcome Analysis

**Date**: April 6, 2026
**Status**: Review and Implementation
**Source**: Analysis of PR #2 "Add test suites (179 tests), fix np.sum crash in diversification, document gaps"

---

## Executive Summary

PR #2 introduced comprehensive testing infrastructure across the entire codebase (previously had zero tests), identified and fixed a critical runtime bug, and documented significant security and quality gaps. This document provides a detailed development roadmap based on those findings.

### Key Achievements from PR #2
- **179 tests added**: 155 backend (pytest) + 24 frontend (vitest)
- **Bug fixed**: NumPy ≥2.0 compatibility issue in `diversification.py`
- **Test isolation**: Proper test database configuration via `conftest.py`
- **Gap identification**: Critical security vulnerabilities documented

---

## Testing Outcome Analysis

### Backend Testing (155 Tests)

#### Test Coverage Breakdown

1. **Services Layer (82 tests)**
   - `vulnerability.py`: 22 tests - MDR curves for seismic/flood/wind perils
   - `stochastic.py`: 17 tests - Monte Carlo simulation engine
   - `pricing.py`: 13 tests - Technical pricing & EP curves
   - `risk_engine.py`: 18 tests - Risk scoring & composition
   - `diversification.py`: 5 tests - Portfolio diversification metrics
   - `geo_processor.py`: 7 tests - Spatial utilities (hexbin, geodataframe)

2. **Models Layer (14 tests)**
   - `schemas.py`: Pydantic validation for all data models
   - Property schemas with boundary validation (lat/lon, TIV)
   - HazardScore, RiskScorecard validation
   - Portfolio and event schemas

3. **Scrapers Layer (24 tests)**
   - `usgs_seismic.py`: PGA estimation at point locations
   - `fema_flood.py`: Flood zone determination
   - `noaa_hurricane.py`: Wind-to-category conversion, risk estimation
   - Network-free unit tests (no external API calls)

4. **API Routes (35 tests)**
   - Property CRUD operations
   - Risk scoring endpoints
   - What-if scenario analysis
   - Data catalog and scrape history
   - Map layers and GeoJSON export

#### Test Infrastructure
- **Database isolation**: Environment variable overrides in `conftest.py`
  - Temporary SQLite DB: `GEORISK_SQLITE_DB`
  - Temporary DuckDB: `GEORISK_DUCKDB_PATH`
  - Isolated catalog directory: `GEORISK_CATALOG_DIR`
- **AsyncIO mode**: Auto-configured in `pytest.ini`
- **No side effects**: Tests never touch development databases

### Frontend Testing (24 Tests)

#### Test Coverage Breakdown

1. **Type Contracts (8 tests)**
   - Interface validation for all TypeScript types
   - Ensures API client contracts match backend schemas

2. **API Client Mocks (13 tests)**
   - Mock tests for all API endpoints
   - Request/response validation
   - Error handling scenarios

3. **Component Rendering (3 tests)**
   - Basic rendering tests with @testing-library/react
   - jsdom environment for DOM manipulation

#### Test Infrastructure
- **Framework**: vitest + @testing-library/react + jsdom
- **Configuration**: `vite.config.ts` with test setup
- **Mock strategy**: Axios-based API client with mock implementations

---

## Bug Fix: NumPy Compatibility

### Issue
`diversification.py` passed a generator expression to `np.sum()`, which raises `TypeError` on NumPy ≥2.0.

### Location
- File: `georisk/backend/app/services/diversification.py`
- Lines affected: Portfolio-level and marginal-PML calculations

### Fix Applied
```python
# Before — crashes with NumPy ≥2.0
portfolio_pml = float(np.sqrt(np.sum(standalone_pmls_arr ** 2) +
    2 * corr_factor * np.sum(
        standalone_pmls_arr[i] * standalone_pmls_arr[j]
        for i in range(n) for j in range(i + 1, n)
    )))

# After — use Python sum() for generator expression
cross_terms = sum(
    standalone_pmls_arr[i] * standalone_pmls_arr[j]
    for i in range(n) for j in range(i + 1, n)
)
portfolio_pml = float(np.sqrt(np.sum(standalone_pmls_arr ** 2) +
    2 * corr_factor * cross_terms))
```

### Impact
- Fixes crash on NumPy 2.x installations
- Maintains mathematical correctness
- Applied to both portfolio and marginal calculations

---

## Critical Gaps Identified

### Security Vulnerabilities (CRITICAL)

#### 1. SQL Injection
**Severity**: CRITICAL
**Files**:
- `georisk/backend/app/api/routes_synthetic.py:225`
- `georisk/backend/app/api/routes_cat.py:146`

**Issue**: f-string query construction with user-controlled WHERE clauses and LIMIT/OFFSET values
```python
# Vulnerable pattern
query = f"SELECT * FROM table WHERE {where} LIMIT {page_size} OFFSET {offset}"
```

**Remediation Required**:
- Use parameterized queries for all DuckDB operations
- Validate and sanitize WHERE clause inputs
- Implement query builder with proper escaping
- Add input validation at API layer

#### 2. No Authentication/Authorization
**Severity**: CRITICAL
**Scope**: ALL endpoints

**Issue**: No authentication mechanism exists on any endpoint

**Remediation Required**:
- Implement JWT or session-based authentication
- Add authorization middleware to FastAPI
- Protect all property and risk endpoints
- Add user roles (admin, analyst, viewer)

#### 3. No File Upload Size Limits
**Severity**: CRITICAL
**Impact**: DoS vulnerability

**Remediation Required**:
- Implement max file size limits in FastAPI
- Add streaming upload handlers
- Validate file types before processing

### High-Priority Security Issues

#### 4. CORS Configuration
**Severity**: HIGH
**File**: `georisk/backend/app/main.py`

**Issue**: `allow_methods=["*"]` permits all HTTP methods

**Remediation**:
- Restrict to required methods: `["GET", "POST", "PUT", "DELETE"]`
- Configure specific origins for production
- Remove wildcard CORS in production

#### 5. Debug Mode Enabled by Default
**Severity**: HIGH
**File**: `georisk/backend/app/config.py`

**Issue**: Application runs with debug=True by default

**Remediation**:
- Set `debug=False` for production
- Use environment-based configuration
- Disable detailed error messages in production

#### 6. No Rate Limiting
**Severity**: HIGH
**Impact**: API abuse, resource exhaustion

**Remediation Required**:
- Implement rate limiting middleware (slowapi/fastapi-limiter)
- Set per-IP and per-user limits
- Add throttling for expensive operations (stochastic simulations)

#### 7. CSV Formula Injection Risk
**Severity**: HIGH
**Files**: Any CSV export functionality

**Issue**: User data exported to CSV without sanitization

**Remediation**:
- Prefix special characters (=, +, -, @) in CSV exports
- Validate cell contents before export
- Add CSV sanitization utility

#### 8. Path Traversal in GeoJSON Loader
**Severity**: HIGH
**File**: Likely in data loading utilities

**Issue**: `load_geojson()` may accept unsanitized file paths

**Remediation**:
- Validate file paths against whitelist
- Use `os.path.abspath()` and check containment
- Reject paths with `..` or absolute paths

### Medium-Priority Issues

#### 9. Broad Exception Handling
**Severity**: MEDIUM
**Pattern**: `except Exception: pass`

**Issue**: Silent failures hide bugs and security issues

**Remediation**:
- Replace with specific exception types
- Log all exceptions
- Return appropriate error responses

#### 10. DuckDB Concurrent Write Safety
**Severity**: MEDIUM
**Scope**: Analytics queries

**Issue**: Potential race conditions with concurrent writes

**Remediation**:
- Implement connection pooling with write locks
- Use WAL mode for SQLite/DuckDB
- Add transaction management

#### 11. No Request Logging
**Severity**: MEDIUM
**Scope**: All endpoints

**Issue**: No audit trail for API requests

**Remediation**:
- Add logging middleware to FastAPI
- Log: timestamp, user, endpoint, response code
- Integrate with structured logging (e.g., structlog)

#### 12. Pydantic V2 Deprecation
**Severity**: MEDIUM
**Files**: All model definitions

**Issue**: Using deprecated `class Config` pattern

**Remediation**:
- Migrate to Pydantic V2 ConfigDict
- Update all model configurations
- Test validation behavior after migration

---

## Detailed Development Roadmap

### Phase 1: Security Hardening (CRITICAL - 2-3 weeks)

#### Milestone 1.1: SQL Injection Prevention
**Priority**: P0 - Critical
**Estimated Effort**: 3-5 days

**Tasks**:
1. Audit all DuckDB query construction
   - [x] Identify vulnerable f-string queries in `routes_synthetic.py`
   - [x] Identify vulnerable f-string queries in `routes_cat.py`
   - [ ] Search for similar patterns in other files

2. Implement parameterized queries
   - [ ] Create DuckDB query builder utility
   - [ ] Replace f-string queries with parameterized versions
   - [ ] Add input validation for WHERE clauses
   - [ ] Implement whitelist for allowed columns/operators

3. Add SQL injection tests
   - [ ] Write tests for malicious WHERE clauses
   - [ ] Test LIMIT/OFFSET injection attempts
   - [ ] Verify query sanitization

4. Code review and validation
   - [ ] Security review of all database interactions
   - [ ] Penetration testing for SQL injection
   - [ ] Document safe query patterns

**Success Criteria**:
- Zero f-string queries with user input
- All queries use parameterization
- Injection tests pass
- Security audit approved

#### Milestone 1.2: Authentication & Authorization
**Priority**: P0 - Critical
**Estimated Effort**: 5-7 days

**Tasks**:
1. Design authentication system
   - [ ] Choose auth strategy (JWT recommended)
   - [ ] Design user schema (username, password_hash, role)
   - [ ] Plan authentication flow

2. Implement authentication
   - [ ] Add user model and database table
   - [ ] Implement password hashing (bcrypt/argon2)
   - [ ] Create login/logout endpoints
   - [ ] Generate and validate JWT tokens
   - [ ] Add authentication middleware

3. Implement authorization
   - [ ] Define role hierarchy (admin, analyst, viewer)
   - [ ] Add role-based access control (RBAC)
   - [ ] Protect endpoints with auth decorators
   - [ ] Implement permission checks

4. Update frontend
   - [ ] Add login UI component
   - [ ] Store JWT in secure storage
   - [ ] Add auth headers to API client
   - [ ] Handle 401/403 responses

5. Testing
   - [ ] Unit tests for auth logic
   - [ ] Integration tests for protected endpoints
   - [ ] Test unauthorized access attempts
   - [ ] Test token expiration and refresh

**Success Criteria**:
- All endpoints require authentication
- Role-based permissions enforced
- Tests cover auth scenarios
- Frontend integrates auth flow

#### Milestone 1.3: Input Validation & File Security
**Priority**: P0 - Critical
**Estimated Effort**: 3-4 days

**Tasks**:
1. File upload security
   - [ ] Add max file size limits (FastAPI settings)
   - [ ] Implement file type validation
   - [ ] Add virus scanning (optional: ClamAV)
   - [ ] Use secure temporary storage

2. Path traversal prevention
   - [ ] Audit all file system operations
   - [ ] Validate paths in `load_geojson()`
   - [ ] Implement path sanitization utility
   - [ ] Test with malicious paths (`../`, absolute paths)

3. CSV export sanitization
   - [ ] Create CSV sanitization function
   - [ ] Prefix formula characters (=, +, -, @)
   - [ ] Apply to all CSV export functions
   - [ ] Test with malicious formulas

**Success Criteria**:
- File uploads limited and validated
- No path traversal vulnerabilities
- CSV exports sanitized
- Security tests pass

#### Milestone 1.4: Production Hardening
**Priority**: P0 - Critical
**Estimated Effort**: 2-3 days

**Tasks**:
1. CORS configuration
   - [ ] Restrict allowed methods to GET, POST, PUT, DELETE
   - [ ] Configure specific allowed origins
   - [ ] Remove wildcard CORS for production

2. Debug mode management
   - [ ] Set debug=False for production
   - [ ] Use environment-based configuration
   - [ ] Implement custom error handlers (hide stack traces)

3. Rate limiting
   - [ ] Install slowapi or fastapi-limiter
   - [ ] Configure global rate limits
   - [ ] Add per-endpoint limits for expensive operations
   - [ ] Test rate limiting behavior

**Success Criteria**:
- CORS properly configured
- Debug mode disabled in production
- Rate limiting active
- Production-ready configuration

---

### Phase 2: API Robustness & Reliability (2-3 weeks)

#### Milestone 2.1: Error Handling & Logging
**Priority**: P1 - High
**Estimated Effort**: 4-5 days

**Tasks**:
1. Replace broad exception handling
   - [ ] Audit all `except Exception: pass` patterns
   - [ ] Replace with specific exception types
   - [ ] Add appropriate error responses
   - [ ] Log all caught exceptions

2. Implement structured logging
   - [ ] Install structlog
   - [ ] Configure logging middleware
   - [ ] Log: timestamp, user, endpoint, status, duration
   - [ ] Add log levels (DEBUG, INFO, WARNING, ERROR)
   - [ ] Configure log rotation

3. Custom exception classes
   - [ ] Create domain-specific exceptions
   - [ ] Implement exception handlers in FastAPI
   - [ ] Return consistent error responses
   - [ ] Add error codes for client handling

**Success Criteria**:
- No silent failures
- All errors logged with context
- Consistent error responses
- Proper log rotation configured

#### Milestone 2.2: Database Management
**Priority**: P1 - High
**Estimated Effort**: 3-4 days

**Tasks**:
1. Connection pooling
   - [ ] Implement SQLite connection pool
   - [ ] Implement DuckDB connection pool
   - [ ] Add write locks for concurrent safety
   - [ ] Configure pool size limits

2. Transaction management
   - [ ] Wrap multi-step operations in transactions
   - [ ] Implement rollback on errors
   - [ ] Add transaction context managers

3. Database migrations
   - [ ] Set up Alembic for migrations
   - [ ] Create initial migration
   - [ ] Document migration process

4. WAL mode
   - [ ] Enable WAL mode for SQLite
   - [ ] Test concurrent read/write performance
   - [ ] Document database configuration

**Success Criteria**:
- Connection pooling implemented
- No race conditions
- Migration system in place
- WAL mode active

#### Milestone 2.3: Pydantic V2 Migration
**Priority**: P1 - High
**Estimated Effort**: 2-3 days

**Tasks**:
1. Update Pydantic models
   - [ ] Replace `class Config` with `ConfigDict`
   - [ ] Update all model definitions
   - [ ] Fix deprecated patterns

2. Test validation behavior
   - [ ] Run full test suite
   - [ ] Verify serialization/deserialization
   - [ ] Check API compatibility

3. Update documentation
   - [ ] Document new patterns
   - [ ] Update examples in README

**Success Criteria**:
- All models use Pydantic V2
- No deprecation warnings
- All tests pass

---

### Phase 3: Test Expansion & Quality (2-3 weeks)

#### Milestone 3.1: Backend Test Coverage
**Priority**: P2 - Medium
**Estimated Effort**: 5-7 days

**Tasks**:
1. Integration tests
   - [ ] End-to-end API workflows
   - [ ] Multi-property portfolio analysis
   - [ ] Scenario comparison workflows

2. Performance tests
   - [ ] Stochastic simulation benchmarks
   - [ ] Large portfolio processing
   - [ ] Concurrent request handling

3. Security tests
   - [ ] SQL injection attempts
   - [ ] XSS prevention tests
   - [ ] Auth bypass attempts
   - [ ] CSRF token validation

4. Edge case testing
   - [ ] Boundary values (extreme lat/lon)
   - [ ] Invalid perils/hazards
   - [ ] Empty portfolios
   - [ ] Large file uploads

**Success Criteria**:
- Test coverage >80%
- Security tests passing
- Performance benchmarks established
- Edge cases covered

#### Milestone 3.2: Frontend Test Expansion
**Priority**: P2 - Medium
**Estimated Effort**: 4-5 days

**Tasks**:
1. Component tests
   - [ ] PropertyList component
   - [ ] RiskScorecard component
   - [ ] Map component
   - [ ] Dashboard components

2. Integration tests
   - [ ] User workflows (add property → view risk)
   - [ ] Map interaction tests
   - [ ] Form submission flows

3. Accessibility tests
   - [ ] ARIA label validation
   - [ ] Keyboard navigation
   - [ ] Screen reader compatibility

4. E2E tests (optional)
   - [ ] Install Playwright
   - [ ] Critical user journeys
   - [ ] Cross-browser testing

**Success Criteria**:
- All major components tested
- User workflows validated
- Accessibility standards met
- E2E tests for critical paths

#### Milestone 3.3: CI/CD Pipeline
**Priority**: P2 - Medium
**Estimated Effort**: 3-4 days

**Tasks**:
1. GitHub Actions setup
   - [ ] Create workflow for backend tests
   - [ ] Create workflow for frontend tests
   - [ ] Add linting (flake8, eslint)
   - [ ] Add type checking (mypy, tsc)

2. Pre-commit hooks
   - [ ] Install pre-commit framework
   - [ ] Add code formatting (black, prettier)
   - [ ] Add import sorting (isort)
   - [ ] Add security checks (bandit)

3. Code coverage reporting
   - [ ] Configure pytest-cov
   - [ ] Configure vitest coverage
   - [ ] Upload to CodeCov or similar
   - [ ] Set coverage thresholds

4. Deployment pipeline
   - [ ] Build Docker images
   - [ ] Run tests in CI
   - [ ] Deploy to staging on PR merge
   - [ ] Deploy to production on release

**Success Criteria**:
- CI runs on all PRs
- Tests must pass to merge
- Code coverage tracked
- Automated deployments

---

### Phase 4: Production Readiness (2-3 weeks)

#### Milestone 4.1: Performance Optimization
**Priority**: P3 - Low
**Estimated Effort**: 5-6 days

**Tasks**:
1. Database optimization
   - [ ] Add indexes for common queries
   - [ ] Optimize slow queries
   - [ ] Implement query caching

2. API optimization
   - [ ] Add response caching (Redis)
   - [ ] Implement pagination for large results
   - [ ] Add query result streaming

3. Frontend optimization
   - [ ] Implement lazy loading
   - [ ] Add code splitting
   - [ ] Optimize bundle size
   - [ ] Add service worker caching

4. Stochastic engine optimization
   - [ ] Profile simulation performance
   - [ ] Optimize hot paths
   - [ ] Consider Numba/Cython for critical code

**Success Criteria**:
- API response time <500ms (p95)
- Frontend load time <2s
- Stochastic simulations <1s for 1000 years
- Resource usage optimized

#### Milestone 4.2: Monitoring & Observability
**Priority**: P3 - Low
**Estimated Effort**: 4-5 days

**Tasks**:
1. Application monitoring
   - [ ] Set up Prometheus/Grafana
   - [ ] Add custom metrics (request count, latency)
   - [ ] Monitor database connections
   - [ ] Track simulation performance

2. Error tracking
   - [ ] Set up Sentry or similar
   - [ ] Track backend errors
   - [ ] Track frontend errors
   - [ ] Configure alerting

3. Health checks
   - [ ] Implement /health endpoint with dependencies
   - [ ] Check database connectivity
   - [ ] Check external API availability
   - [ ] Add readiness/liveness probes

4. Log aggregation
   - [ ] Set up ELK stack or similar
   - [ ] Centralize backend logs
   - [ ] Centralize frontend logs
   - [ ] Create dashboards

**Success Criteria**:
- Real-time metrics visible
- Errors tracked and alerted
- Health checks operational
- Logs centralized

#### Milestone 4.3: Documentation & Training
**Priority**: P3 - Low
**Estimated Effort**: 4-5 days

**Tasks**:
1. API documentation
   - [ ] Generate OpenAPI/Swagger docs
   - [ ] Add endpoint descriptions
   - [ ] Include request/response examples
   - [ ] Document error codes

2. Developer documentation
   - [ ] Setup guide (local development)
   - [ ] Architecture overview
   - [ ] Testing guide
   - [ ] Deployment guide

3. User documentation
   - [ ] User guide for risk analysis
   - [ ] Tutorial videos
   - [ ] FAQ section
   - [ ] Example workflows

4. Security documentation
   - [ ] Security architecture
   - [ ] Threat model
   - [ ] Incident response plan
   - [ ] Penetration test reports

**Success Criteria**:
- API docs auto-generated
- Developer onboarding smooth
- User guide comprehensive
- Security posture documented

---

## Test Execution Strategy

### Running Tests

#### Backend Tests
```bash
cd georisk/backend
python -m pytest tests/ -v
```

**Test Isolation**:
- Uses temporary databases via `conftest.py`
- No external API calls (mocked)
- Safe to run in any environment

#### Frontend Tests
```bash
cd georisk/frontend
npx vitest run
```

**Test Environment**:
- jsdom for DOM simulation
- Mock API responses
- No backend dependency

### Continuous Testing
- Run tests on every commit (pre-commit hook)
- Run full suite in CI on PR
- Run integration tests on staging deployment
- Run smoke tests on production deployment

---

## Risk Management

### Implementation Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQL injection exploited before fix | High | Critical | Fast-track Milestone 1.1 |
| Auth implementation delays | Medium | High | Use proven library (FastAPI-Users) |
| Test suite slows down development | Medium | Medium | Optimize tests, use parallel execution |
| Database migration issues | Low | High | Test migrations in staging first |
| Performance regression | Medium | Medium | Establish benchmarks, monitor metrics |

### Technical Debt

Current technical debt identified:
1. **No authentication** - Blocking production deployment
2. **SQL injection vulnerabilities** - Security critical
3. **Broad exception handling** - Maintainability issue
4. **No logging** - Operational blindness
5. **Deprecated Pydantic patterns** - Future upgrade risk

**Debt Paydown Strategy**:
- Address security debt immediately (Phase 1)
- Fix operational debt in Phase 2
- Clean up code quality debt in Phase 3

---

## Success Metrics

### Phase 1 (Security)
- [ ] Zero critical security vulnerabilities
- [ ] All endpoints authenticated
- [ ] SQL injection tests passing
- [ ] Security audit approved

### Phase 2 (Robustness)
- [ ] No silent failures (all exceptions logged)
- [ ] 99.9% uptime (after monitoring setup)
- [ ] <1% error rate
- [ ] Structured logs in place

### Phase 3 (Quality)
- [ ] >80% test coverage
- [ ] CI/CD pipeline operational
- [ ] All PRs tested automatically
- [ ] Code coverage trending up

### Phase 4 (Production)
- [ ] <500ms API response time (p95)
- [ ] <2s frontend load time
- [ ] Monitoring dashboards live
- [ ] Documentation complete

---

## Resources & Dependencies

### Team Requirements
- **Backend Engineer**: Focus on security, API, database
- **Frontend Engineer**: Focus on UI tests, auth integration
- **DevOps Engineer**: Focus on CI/CD, monitoring, deployment
- **Security Specialist**: Focus on penetration testing, audit

### Technology Stack Additions
- **Authentication**: FastAPI-Users or similar
- **Rate Limiting**: slowapi or fastapi-limiter
- **Logging**: structlog
- **Monitoring**: Prometheus + Grafana
- **Error Tracking**: Sentry
- **Database Migrations**: Alembic

### External Dependencies
- No new external data sources required
- Existing USGS/FEMA/NOAA scrapers adequate
- May need third-party auth provider (optional)

---

## Conclusion

PR #2 established a strong testing foundation and exposed critical security gaps that must be addressed before production deployment. This development plan provides a clear, phased approach to:

1. **Secure the application** (Phase 1 - CRITICAL)
2. **Improve reliability** (Phase 2)
3. **Expand test coverage** (Phase 3)
4. **Prepare for production** (Phase 4)

**Immediate Next Steps**:
1. Review and approve this development plan
2. Prioritize Phase 1 security work
3. Assign team members to milestones
4. Begin Milestone 1.1 (SQL Injection Prevention)
5. Set up project tracking (Jira/GitHub Projects)

**Estimated Total Timeline**: 8-12 weeks for all 4 phases

---

## Appendix A: Test Files Added

### Backend Test Files
- `georisk/backend/pytest.ini`
- `georisk/backend/tests/__init__.py`
- `georisk/backend/tests/conftest.py`
- `georisk/backend/tests/test_api_routes.py` (177 lines, 35 tests)
- `georisk/backend/tests/test_diversification.py` (99 lines, 5 tests)
- `georisk/backend/tests/test_geo_processor.py` (61 lines, 7 tests)
- `georisk/backend/tests/test_pricing.py` (131 lines, 13 tests)
- `georisk/backend/tests/test_risk_engine.py` (153 lines, 18 tests)
- `georisk/backend/tests/test_schemas.py` (142 lines, 14 tests)
- `georisk/backend/tests/test_scrapers.py` (123 lines, 24 tests)
- `georisk/backend/tests/test_stochastic.py` (220 lines, 17 tests)
- `georisk/backend/tests/test_vulnerability.py` (160 lines, 22 tests)

### Frontend Test Files
- `georisk/frontend/vite.config.ts` (updated with test config)
- `georisk/frontend/package.json` (added vitest dependencies)
- Frontend test files (not shown in PR diff, but mentioned in description)

## Appendix B: Bug Fix Details

**File**: `georisk/backend/app/services/diversification.py`

**Problem**: Generator expression passed to `np.sum()` fails on NumPy ≥2.0

**Solution**: Extract generator to Python `sum()`, pass result to `np.sum()`

**Affected Functions**:
- `compute_diversification()` - Portfolio-level PML calculation
- `compute_diversification()` - Marginal PML calculation (within loop)

**Testing**: Added 5 tests in `test_diversification.py` to prevent regression

---

*Document Version 1.0 - Generated from PR #2 analysis*
