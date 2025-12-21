# Refactoring Plan: Step-by-Step with Testing

## 📋 Current State Analysis

### What We Have (from old index.py)
- **9 API endpoints** 
- **10 handler methods**
- **8 utility methods**
- **7 fish species columns** in database

### What's Missing in Refactored Code
- ❌ Missing 5 API endpoints: `/api/yearly`, `/api/trend`, `/api/species`, `/api/monthly`, `/api/map_data`, `/api/filter_options`
- ❌ Wrong database schema (using `total_catch` instead of individual species columns)
- ❌ Missing helper methods: `build_where_clause()`, `get_species_list()`

## 🎯 Refactoring Strategy

We'll port functionality in **6 phases**, testing after each phase:

---

## **PHASE 1: Fix Database Module** ⚙️
**Goal:** Update database.py to use correct schema (species columns, not total_catch)

### Changes Needed:
- Update `get_statistics()` to sum species columns
- Update `get_catch_areas()` to sum species columns  
- Add utility functions: `get_species_list()`, `get_species_columns()`

### Files Modified:
- `app/database.py`

### Test Commands:
```bash
python3 -c "
from app import database
stats = database.get_statistics()
print('Stats:', stats)
areas = database.get_catch_areas()
print('Areas:', len(areas))
"
```

### Success Criteria:
- ✅ No "total_catch" errors
- ✅ Statistics return valid numbers
- ✅ Catch areas list loads

**Estimated Time:** 15 minutes

---

## **PHASE 2: Add Query Builder Utilities** 🔧
**Goal:** Add WHERE clause builder and filter helpers

### Changes Needed:
- Add `build_where_clause()` to database.py
- Add `get_species_list()` to database.py
- Add `get_species_columns()` to database.py

### Files Modified:
- `app/database.py`

### Test Commands:
```bash
python3 -c "
from app.database import build_where_clause, get_species_list
params = {'species': ['chinook', 'coho'], 'year': ['2023']}
where, vals = build_where_clause(params)
print('WHERE:', where)
print('Species:', get_species_list(params))
"
```

### Success Criteria:
- ✅ WHERE clauses build correctly
- ✅ Species filtering works
- ✅ No import errors

**Estimated Time:** 20 minutes

---

## **PHASE 3: Add Missing API Endpoints (Part 1)** 📡
**Goal:** Add filter_options and yearly endpoints

### Changes Needed:
- Add `serve_filter_options()` to server.py
- Add `serve_yearly_data()` to server.py
- Wire up routes in `do_GET()`

### Files Modified:
- `app/server.py`

### Test Commands:
```bash
# Start server: python run.py

# In another terminal:
curl http://localhost:8080/api/filter_options
curl http://localhost:8080/api/yearly?species=chinook
```

### Success Criteria:
- ✅ `/api/filter_options` returns years, areas, species
- ✅ `/api/yearly` returns aggregated data
- ✅ Browser console shows fewer 404 errors

**Estimated Time:** 25 minutes

---

## **PHASE 4: Add Missing API Endpoints (Part 2)** 📊
**Goal:** Add trend, species, monthly endpoints

### Changes Needed:
- Add `serve_trend_data()` to server.py
- Add `serve_species_totals()` to server.py
- Add `serve_monthly_data()` to server.py
- Wire up routes in `do_GET()`

### Files Modified:
- `app/server.py`

### Test Commands:
```bash
curl http://localhost:8080/api/trend?time_unit=yearly&species=chinook
curl http://localhost:8080/api/species?species=chinook&species=coho
curl http://localhost:8080/api/monthly?species=chinook
```

### Success Criteria:
- ✅ Trend data returns time series
- ✅ Species totals return correctly
- ✅ Monthly aggregation works
- ✅ Charts start rendering in browser

**Estimated Time:** 30 minutes

---

## **PHASE 5: Add Map Data Endpoint** 🗺️
**Goal:** Get map working with area data

### Changes Needed:
- Add `serve_map_data()` to server.py
- Add `serve_top_areas()` to server.py (if needed)
- Wire up routes

### Files Modified:
- `app/server.py`

### Test Commands:
```bash
curl http://localhost:8080/api/map_data?species=chinook&species=coho
curl http://localhost:8080/api/areas?species=chinook
```

### Success Criteria:
- ✅ Map data endpoint returns area totals
- ✅ Map polygons show correct colors
- ✅ Custom areas display properly

**Estimated Time:** 20 minutes

---

## **PHASE 6: Integration Testing & Cleanup** ✅
**Goal:** Full end-to-end testing and polish

### Changes Needed:
- Test all filter combinations
- Verify all charts render
- Check map interactions
- Test auto-update
- Clean up any console warnings

### Test Commands:
```bash
# Full integration test script
python3 test_integration.py

# Manual browser testing:
# 1. Load http://localhost:8080
# 2. Test all filters
# 3. Test all charts
# 4. Test map clicks
# 5. Test auto-update
```

### Success Criteria:
- ✅ Zero console errors
- ✅ All charts render
- ✅ All filters work
- ✅ Map fully interactive
- ✅ Stats display correctly
- ✅ Auto-update works

**Estimated Time:** 20 minutes

---

## 📝 Complete Checklist

### Database Module (`app/database.py`)
- [ ] Fix `get_statistics()` to use species columns
- [ ] Fix `get_catch_areas()` to use species columns
- [ ] Add `build_where_clause(params)`
- [ ] Add `get_species_list(params)`
- [ ] Add `get_species_columns()`
- [ ] Add `get_filtered_records(params)` (if needed)

### Server Module (`app/server.py`)
- [ ] Update existing `serve_statistics()`
- [ ] Update existing `serve_areas()`
- [ ] Add `serve_filter_options()`
- [ ] Add `serve_yearly_data(params)`
- [ ] Add `serve_trend_data(params)`
- [ ] Add `serve_species_totals(params)`
- [ ] Add `serve_monthly_data(params)`
- [ ] Add `serve_map_data(params)`
- [ ] Add routes for all new endpoints

### Testing
- [ ] Phase 1: Database functions work
- [ ] Phase 2: Query builders work
- [ ] Phase 3: Filter options & yearly work
- [ ] Phase 4: Trend, species, monthly work
- [ ] Phase 5: Map data works
- [ ] Phase 6: Full integration test passes

---

## 🚀 Execution Plan

### Session 1 (Today - ~1 hour)
- ✅ Complete Phase 1: Fix database module
- ✅ Complete Phase 2: Add query builders
- ✅ Test with user

### Session 2 (Next - ~1 hour)
- Complete Phase 3: Add filter_options & yearly
- Complete Phase 4: Add trend, species, monthly
- Test with user

### Session 3 (Final - ~30 min)
- Complete Phase 5: Add map data
- Complete Phase 6: Integration testing
- Deploy to Cloud Run

---

## 📊 Progress Tracking

| Phase | Status | Test Status | Notes |
|-------|--------|-------------|-------|
| Phase 1: Database | ⏳ Not Started | ⏳ | |
| Phase 2: Query Builders | ⏳ Not Started | ⏳ | |
| Phase 3: API Part 1 | ⏳ Not Started | ⏳ | |
| Phase 4: API Part 2 | ⏳ Not Started | ⏳ | |
| Phase 5: Map Data | ⏳ Not Started | ⏳ | |
| Phase 6: Integration | ⏳ Not Started | ⏳ | |

Legend: ⏳ Not Started | 🔄 In Progress | ✅ Complete | ❌ Failed

---

## 🎯 Success Metrics

When refactoring is complete:
- ✅ Zero browser console errors
- ✅ Zero server errors  
- ✅ All API endpoints return 200
- ✅ All charts render correctly
- ✅ Map is fully interactive
- ✅ Filters work correctly
- ✅ Code is modular and testable

---

## 🔄 Rollback Plan

At any phase, if issues arise:
1. Stop current work
2. Run original: `python index.py`
3. Debug issue
4. Continue when ready

---

## 📞 Communication Protocol

After each phase:
1. I'll implement the changes
2. I'll provide updated files
3. You test using the test commands
4. You report: ✅ Working or ❌ Issues
5. We fix issues before moving to next phase

---

## Ready to Start?

Say "Let's start Phase 1" and I'll begin fixing the database module!
