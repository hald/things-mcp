# Pull Request Template

Use this template when creating your PR on GitHub!

---

## Title
```
Add human-readable age display for created and modified dates
```

## Description

### Summary
This PR adds human-readable age calculation and display for task creation and modification dates, making it easier for users to identify stale tasks and track when items were last updated.

### What's New

**Age Calculation Feature:**
- Tasks now display "Age: X ago" showing time since creation
- Tasks now display "Last modified: X ago" showing time since last update
- Ages are shown in natural, human-readable language (e.g., "3 days ago", "2 weeks ago")

**Example Output:**
```
Title: Prepare presentation
Created: 2025-11-09T10:30:00
Age: 1 week ago
Modified: 2025-11-15T14:20:00
Last modified: 1 day ago
```

### Benefits
- **Identify stale tasks** - Quickly see which tasks have been sitting for a long time
- **Track activity** - Know when tasks were last updated
- **Better prioritization** - Make informed decisions based on task age
- **Improved user experience** - Natural language is more intuitive than raw timestamps

### Implementation Details

**Code Quality Improvements:**
- Extracted age calculation logic into reusable `_calculate_age()` helper function
- Added proper type hints and comprehensive docstrings
- Improved error handling from bare `except:` to specific `except (ValueError, TypeError):`
- Follows DRY principle for maintainable code

**Age Display Formats:**
- Same day: "today"
- Recent days: "3 days ago" (2-6 days)
- Recent weeks: "2 weeks ago" (7-29 days)  
- Recent months: "3 months ago" (30-364 days)
- Years: "2 years ago" (365+ days)

### Testing
Added **19 comprehensive test cases** covering:
- All age calculation scenarios (days, weeks, months, years)
- Edge cases (today, 1 day, 1 week, 1 year)
- Error handling for invalid dates
- Integration with todo formatting
- Both creation age and modification age display

**Test Files:**
- `test_formatters.py` - New `TestCalculateAge` class with 13 tests
- `test_formatters.py` - 6 additional tests in `TestFormatTodo` class

All tests pass successfully.

### Files Changed
- `formatters.py` - Added `_calculate_age()` helper and age display logic
- `test_formatters.py` - Added comprehensive test coverage (19 tests)
- `README.md` - Documented the new feature with examples and use cases

### Backward Compatibility
✅ **Fully backward compatible** - Only adds new information, doesn't change existing functionality

### Documentation
- Updated README.md with new "Task Age Display" section
- Added example outputs showing the feature
- Added new sample usage queries
- Added tips for using age information

---

## Checklist
- [x] Code follows project style and conventions
- [x] Added comprehensive test coverage (19 tests)
- [x] All tests pass
- [x] Updated README.md with feature documentation
- [x] Added proper docstrings and type hints
- [x] Improved error handling (specific exceptions)
- [x] Non-breaking change (backward compatible)
- [x] Feature adds genuine value to users

## Screenshots/Examples

### Before:
```
Title: Buy groceries
Created: 2025-11-09T10:30:00
Modified: 2025-11-15T14:20:00
```

### After:
```
Title: Buy groceries
Created: 2025-11-09T10:30:00
Age: 1 week ago
Modified: 2025-11-15T14:20:00
Last modified: 1 day ago
```

---

## Additional Notes

This feature was developed with a focus on code quality, maintainability, and comprehensive testing. The helper function approach makes it easy to modify age display logic in the future, and the extensive test coverage ensures reliability.

Happy to make any adjustments based on feedback!
