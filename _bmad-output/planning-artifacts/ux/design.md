# Expense Tracker - Design Document

**Created:** 2026-11-25  
**Status:** draft

---

## Overview

This document defines the visual design specifications for the Expense Tracker application. See [EXPERIENCE.md](./experience.md) for the complete user experience design, user journeys, and interaction design details.

## Design Decisions

### Architecture
- **Monolithic SPA**: Single-page application with client-side routing
- **Component-based UI**: Reusable React components following atomic design principles
- **Database**: SQLite with Prisma ORM for type-safe database access

### Visual Design
- Clean, minimalist aesthetic with ample white space
- Trust-building blue color palette (#3B82F6 primary)
- System font stack for performance
- 16px baseline spacing for consistency

### Data Model
```
Expense {
  id: AutoIncrement
  amount: Decimal (> 0)
  category: String
  description?: String
  created_at: DateTime (auto)
  updated_at: DateTime (auto)
}
```

## References
- Full UX specification: `EXPERIENCE.md`
- Information architecture and UI components documented in EXPERIENCE.md