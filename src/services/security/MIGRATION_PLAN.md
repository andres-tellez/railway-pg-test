# Security Services Migration Plan

**Status:** Planning Phase
**Risk Level:** Very Low (incremental, backward compatible)

## Overview

This document outlines the safe, incremental migration of security utilities from `src/utils/` to `src/services/security/`.

## Principles

1. **Zero Breaking Changes** - Existing code works unchanged
2. **Additive Only** - New structure, no deletions
3. **Gradual Migration** - One service at a time
4. **Test Each Step** - Verify before proceeding

## Migration Phases

### Phase 1: Foundation ✅ (Complete)
- [x] Create directory structure
- [x] Add package initialization
- [x] Create documentation

### Phase 2: New Services (In Progress)
- [x] Create OpenAI rate limiter (Step 1: Rate limiting)
- [x] Test independently
- [x] Integrate into conversation routes
- [ ] Create OpenAI cost tracking (Step 2: Cost limits)
- [ ] Integrate cost tracking

### Phase 3: Rate Limiting Consolidation (Future)
- [ ] Create unified rate limiting service
- [ ] Wrap existing rate limiters
- [ ] Migrate one route at a time
- [ ] Test each migration

### Phase 4: Authentication Services (Future)
- [ ] Create JWT service wrapper
- [ ] Migrate routes gradually
- [ ] Test thoroughly

### Phase 5: Authorization Services (Future)
- [ ] Create authorization service
- [ ] Migrate decorators
- [ ] Test authorization logic

### Phase 6: Input Validation Services (Future)
- [ ] Create request validation service
- [ ] Migrate sanitization utilities
- [ ] Test validation logic

### Phase 7: Audit Monitoring Services (Future)
- [ ] Create audit logging service
- [ ] Add security monitoring
- [ ] Test monitoring functionality

### Phase 8: Encryption Services (Future)
- [ ] Create encryption service wrapper
- [ ] Add key management
- [ ] Test encryption/decryption

### Phase 9: Request Security Services (Future)
- [ ] Create security headers service
- [ ] Migrate CORS configuration
- [ ] Test request security

### Phase 10: Cost Tracking Services (Future)
- [ ] Create cost tracking service
- [ ] Add budget management
- [ ] Test cost tracking

## Migration Checklist Template

For each service migration:

- [ ] Create new service file
- [ ] Wrap existing utility (backward compatible)
- [ ] Write unit tests
- [ ] Test in isolation
- [ ] Migrate one route/usage
- [ ] Test migrated route
- [ ] Migrate remaining routes
- [ ] Update documentation
- [ ] Mark old utility as deprecated (future)

## Current Security Utilities

| Utility | Location | Usage Count | Migration Priority |
|---------|----------|-------------|-------------------|
| `auth0_jwt.py` | `src/utils/` | 13+ files | Medium |
| `auth_rate_limiter.py` | `src/utils/` | 4 files | Low |
| `rate_limiter.py` | `src/utils/` | 3 files | Low |
| `authorization.py` | `src/utils/` | Routes | Medium |
| `security_utils.py` | `src/utils/` | 5 files | Low |
| `token_encryption.py` | `src/utils/` | Models | Low |
| `audit_logger.py` | `src/utils/` | Auth routes | Low |
| `oauth_state_manager.py` | `src/utils/` | OAuth routes | Low |

## Notes

- Migration is **optional** - existing code works fine
- New features should use new structure
- Old code can be migrated when convenient
- No rush - safety first
