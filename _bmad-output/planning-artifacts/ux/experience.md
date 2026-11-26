# Expense Tracker - Experience Document

**Created:** 2026-11-25  
**Status:** draft

---

## User Experience Vision

A clean, intuitive, single-page application that makes expense tracking effortless. Users should be able to log an expense in under 5 seconds while maintaining a delightful, trustworthy experience.

---

## User Journeys

### Journey 1: Daily Expense Logging (Primary)

**User:** Sarah (Budget-conscious individual)

```
1. Sarah opens Expense Tracker in her browser
2. She clicks on the floating action button (FAB)
3. She immediately sees the "Add Expense" form
4. She selects "Food" from category dropdown
5. She enters $12.50
6. She adds "Lunch with colleague"
7. She clicks Save
8. She sees a brief success animation
9. The expense appears in her list below
```

**Key Moments:**
- Form should be pre-focused on amount field
- Date defaults to today, but can be changed
- Quick access to common categories
- Success feedback is immediate but unobtrusive

### Journey 2: Monthly Review (Secondary)

**User:** Mike (Small business owner)

```
1. Mike opens Expense Tracker
2. He navigates to Dashboard
3. He sees current month total: $1,200
4. He clicks "View Details"
5. He sees category breakdown as pie chart
6. He filters by "Business" expenses
7. He exports to CSV for accounting
```

**Key Moments:**
- Dashboard cards should be scannable at a glance
- Visual hierarchy should guide to actionable insights
- Export should be discoverable but not dominant

---

## Information Architecture

```
/ (Dashboard)
├── Today's Total
├── Weekly/Monthly Summary Cards
├── Recent Expenses (list)
└── Category Breakdown (chart)

/expenses
├── All Expenses (table)
├── Filter Bar (date range, category, payment method)
├── Add Expense (modal or dedicated page)

/categories
├── Manage Categories
├── Add New Category

/settings
├── Theme (Light/Dark)
├── Currency
└── Export Data
```

---

## UI Components

### Core Components

1. **DashboardCard**
   - Displays summary total for a time period
   - Shows trend indicator
   - Clickable to drill down

2. **ExpenseList**
   - Table view with columns: Date, Category, Amount, Description, Payment Method
   - Sortable headers
   - Empty state when no expenses

3. **AddExpenseForm**
   - Modal or inline form
   - All required fields
   - Form validation
   - Auto-focus on first field

4. **CategoryFilter**
   - Dropdown with categories
   - "All Categories" option
   - Badge display of selected category

5. **DateRangePicker**
   - Quick select: Today, Week, Month
   - Custom range option
   - Visual calendar icon

### Layout

- **Mobile First:** Single column layout
- **Desktop:** Responsive grid (sidebar or top nav)
- **Spacing:** Consistent 16px baseline
- **Typography:** System font stack for performance
- **Colors:** 
  - Primary: Trustworthy blue (#3B82F6)
  - Success: Green (#10B981)
  - Warning: Amber (#F59E0B)
  - Background: Light mode (#F9FAFB), Dark mode (#111827)

---

## Interaction Design

### Micro-interactions

1. **Add Expense Success**
   - Brief "Expense added!" toast (2 seconds)
   - Form resets and closes
   - List scrolls to show new entry (smooth scroll)

2. **Edit Expense**
   - Form transitions in with fade + slide
   - On save: row updates in place with smooth transition

3. **Delete Expense**
   - Row slides out, replaced by confirmation bar
   - Undo available for 3 seconds

4. **Filter Changes**
   - Results fade out, filter chips update, results fade in
   - Loading state for large datasets

---

## Visual Design

### Color Palette
- Primary: #3B82F6 (Blue 500)
- Secondary: #6B7280 (Gray 500)
- Success: #10B981 (Green 500)
- Warning: #F59E0B (Amber 500)
- Background: #F9FAFB (Gray 50) / #111827 (Gray 900)
- Surface: #FFFFFF (White) / #1F2937 (Gray 800)

### Typography
- Font family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif
- Display (Dashboard totals): 32px / 24px / 18px / 16px
- Heading: 20px / 16px / 14px
- Body: 16px
- Label: 12px

### Iconography
- Feather Icons or similar lightweight icon set
- Consistent stroke width (2px)
- Color: inherited from current context

---

## Accessibility

### Requirements
- WCAG 2.1 AA compliance
- Keyboard navigation: Tab order follows visual flow
- Focus indicators: visible on all interactive elements
- ARIA labels for icon buttons
- Color contrast: minimum 4.5:1 for normal text

### Components
- All form fields have associated labels
- Tables have proper headers and scope attributes
- Charts have alternative text descriptions
- Color is not the only indicator of state

---

## Responsive Breakpoints
- Mobile: < 640px (320px min)
- Tablet: 640px - 1024px
- Desktop: > 1024px

### Mobile Layout
- Fixed bottom navigation or hamburger menu
- FAB for primary action
- Single column content
- Touch targets: minimum 44px

### Desktop Layout
- Sidebar navigation
- Dashboard grid with multiple cards
- Table with additional columns

---

## Edge Cases & Error States

1. **Empty State**
   - Friendly illustration
   - Clear next step: "Add your first expense"
   - CTAs to get started

2. **No Internet / Offline**
   - Service worker caches core assets
   - Local data still accessible
   - Gentle reminder when back online

3. **Database Error**
   - Clear error message
   - Retry option
   - Instructions to clear cache if needed

4. **Form Validation**
   - Inline error messages
   - Red border on invalid fields
   - Prevent submission until valid