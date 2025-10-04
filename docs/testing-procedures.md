# Testing Procedures: Old vs New Functionality

## 🎯 Overview
This document outlines comprehensive testing procedures to compare old vs new functionality in the SmartCoach application.

## 📋 Pre-Testing Checklist

### Environment Setup
- [ ] Backend server running on `localhost:5000`
- [ ] Frontend server running on `localhost:3000`
- [ ] Database properly seeded with test data
- [ ] Auth0 configured for authentication testing
- [ ] OpenAI API key configured for GPT functionality

### Test Data Requirements
- [ ] At least one authenticated user account
- [ ] Sample athlete data (activities, plans)
- [ ] Test race dates and distances

## 🧪 Manual Testing Procedures

### 1. Frontend Route Testing

#### Test Case 1.1: New `/ask` Route Functionality
```bash
# Steps:
1. Navigate to http://localhost:3000/ask
2. Verify authentication redirect (if not logged in)
3. Login with test account
4. Verify AskGptMvpUI component loads
5. Test question input functionality
6. Submit a test question
7. Verify GPT response appears
8. Test error handling (network issues, invalid inputs)

# Expected Results:
- Route requires authentication
- Component renders correctly
- GPT responses are formatted properly
- Error states are handled gracefully
```

#### Test Case 1.2: Route Navigation Consistency
```bash
# Steps:
1. Test navigation between all routes:
   - / → /home → /ask → /plan → /plan/overview
2. Verify back/forward browser navigation
3. Test direct URL access to protected routes
4. Verify authentication state persistence

# Expected Results:
- All routes accessible when authenticated
- Navigation works smoothly
- Authentication persists across routes
```

### 2. Backend Endpoint Testing

#### Test Case 2.1: `/ask` Endpoint Functionality
```bash
# Test with curl or Postman:

# Valid request
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"question": "How am I doing this week?", "athlete_id": 123}'

# Invalid requests
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "", "athlete_id": 123}'

curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Test", "athlete_id": -1}'

# Expected Results:
- Valid request returns 200 with GPT response
- Invalid requests return appropriate error codes
- Response format matches expected structure
```

#### Test Case 2.2: Training Plan Endpoints
```bash
# Test plan generation
curl -X POST http://localhost:5000/api/plan/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"race_date": "2025-12-01", "race_distance": "Marathon", "user_id": "USER_UUID"}'

# Test current plan retrieval
curl -X GET http://localhost:5000/api/plan/current \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Expected Results:
- Plan generation returns plan_id
- Current plan endpoint returns user's latest plan
- Authentication required for all endpoints
```

### 3. Integration Testing

#### Test Case 3.1: End-to-End User Flow
```bash
# Complete user journey:
1. User logs in via Auth0
2. User navigates to /ask
3. User asks a question about their training
4. System retrieves user's recent activities
5. System calls GPT with formatted prompt
6. System returns formatted response to user
7. User can ask follow-up questions
8. User navigates to other parts of app

# Expected Results:
- Smooth user experience throughout
- Data flows correctly between components
- No authentication issues
- GPT responses are relevant and helpful
```

#### Test Case 3.2: Data Consistency
```bash
# Verify data consistency:
1. Check that activity data shown in /ask matches /plan data
2. Verify user profile data is consistent across endpoints
3. Test with different user accounts
4. Verify data updates are reflected across all views

# Expected Results:
- Data is consistent across all views
- User isolation works correctly
- Updates propagate properly
```

## 🔍 Automated Testing

### Running Test Suites
```bash
# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_frontend_routes.py -v
pytest tests/test_endpoint_comparison.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Performance Testing
```bash
# Run performance benchmarks
pytest tests/test_endpoint_comparison.py::TestPerformanceComparison -v

# Load testing (if implemented)
# Use tools like Apache Bench or Artillery for load testing
```

## 📊 Comparison Metrics

### Key Metrics to Track
1. **Response Times**
   - `/ask` endpoint response time
   - Frontend route loading time
   - GPT API response time

2. **Error Rates**
   - Authentication failures
   - GPT API failures
   - Database connection issues

3. **User Experience**
   - Page load times
   - Navigation smoothness
   - Error message clarity

4. **Data Accuracy**
   - GPT response relevance
   - Activity data accuracy
   - User profile consistency

## 🚨 Regression Testing

### Before Each Release
- [ ] Run full test suite
- [ ] Test all user flows manually
- [ ] Verify performance benchmarks
- [ ] Check error handling scenarios
- [ ] Test with different user roles/permissions

### Critical Test Scenarios
1. **Authentication Edge Cases**
   - Token expiration
   - Invalid tokens
   - Network connectivity issues

2. **GPT Integration**
   - API rate limiting
   - Invalid responses
   - Network timeouts

3. **Database Operations**
   - Connection failures
   - Data corruption
   - Concurrent access

## 📝 Test Documentation

### Bug Reports Template
```markdown
**Bug Report: [Title]**

**Environment:**
- Browser: [Browser and version]
- OS: [Operating System]
- Backend: [Commit hash]
- Frontend: [Commit hash]

**Steps to Reproduce:**
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Result:**
[What should happen]

**Actual Result:**
[What actually happened]

**Screenshots/Logs:**
[Attach relevant files]
```

### Test Results Template
```markdown
**Test Results: [Date]**

**Test Suite:** [Suite Name]
**Environment:** [Environment Details]

**Results Summary:**
- Total Tests: [Number]
- Passed: [Number]
- Failed: [Number]
- Skipped: [Number]

**Failed Tests:**
- [Test Name]: [Reason]

**Performance Metrics:**
- Average Response Time: [Time]
- Error Rate: [Percentage]

**Recommendations:**
- [Any recommendations for improvements]
```

## 🔧 Troubleshooting

### Common Issues
1. **Authentication Problems**
   - Check Auth0 configuration
   - Verify JWT token validity
   - Check CORS settings

2. **GPT API Issues**
   - Verify API key configuration
   - Check rate limiting
   - Monitor API usage

3. **Database Issues**
   - Check connection strings
   - Verify database migrations
   - Check data integrity

### Debug Tools
- Browser Developer Tools
- Network tab for API calls
- Console for JavaScript errors
- Backend logs for server issues
