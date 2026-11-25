# Expense Tracker - Architecture Document

**Created:** 2026-11-25  
**Status:** draft

---

## System Overview

The Expense Tracker is a modern web application built with React and TypeScript, using SQLite as the local database backend. The architecture follows a single-source-of-truth pattern with local-first design principles.

---

## Decision Log

| # | Decision | Status | Context |
|---|----------|--------|---------|
| D001 | Use React with TypeScript | Accepted | Type safety and component ecosystem |
| D002 | Use SQLite via better-sqlite3 | Accepted | Local persistence, ACID transactions |
| D003 | Single-page application architecture | Accepted | Fast interactions, offline support |
| D004 | Component-based architecture | Accepted | Reusability and maintainability |
| D005 | Context API for state management | Accepted | Simplicity for app of this scale |
| D006 | Vite as build tool | Accepted | Fast HMR, modern defaults |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Browser (Client)                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │   React App     │  │  Service Worker │  │   IndexedDB    │ │
│  │  (UI Layer)     │  │ (Offline Cache) │  │ (Fallback DB)  │ │
│  └────────┬────────┘  └─────────────────┘  └────────────────┘ │
│           │                                                        │
│  ┌────────▼─────────────────────────────────────────────────────┐  │
│  │                   Database Layer                            │  │
│  │  ┌──────────────────┐  ┌─────────────────────────────────┐  │  │
│  │  │  SQLite (local)  │  │  better-sqlite3 (Node/WASM)   │  │  │
│  │  └──────────────────┘  └─────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Frontend
- **Framework:** React 18+ with TypeScript 5+
- **Build Tool:** Vite
- **Language:** TypeScript (strict mode)
- **Styling:** CSS Modules or Tailwind CSS
- **State Management:** React Context API + useReducer
- **Routing:** React Router v6 (SPA navigation)

### Backend/Storage
- **Database:** SQLite 3.x
- **Database Binding:** better-sqlite3 (Node.js) or sql.js (WebAssembly)
- **OR / Data Access:** Custom repository pattern

### Testing
- **Unit:** Jest + React Testing Library
- **Integration:** Testing Library
- **E2E:** Playwright (future phase)

### Build & Deployment
- **Bundler:** Vite (Rollup under the hood)
- **Dev Server:** Vite dev server
- **Testing:** Vitest (for faster feedback)

---

## Data Model

### Database Schema

```sql
-- Categories table
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    user_defined INTEGER DEFAULT 0, -- 0 = pre-defined, 1 = user added
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Payment methods table
CREATE TABLE payment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    user_defined INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Expenses table
CREATE TABLE expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL, -- ISO 8601 date string
    category_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    description TEXT,
    payment_method_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id) ON DELETE RESTRICT
);

-- Indexes for performance
CREATE INDEX idx_expenses_date ON expenses(date);
CREATE INDEX idx_expenses_category ON expenses(category_id);
CREATE INDEX idx_expenses_amount ON expenses(amount);
```

### Data Models (TypeScript)

```typescript
interface Category {
  id: number;
  name: string;
  userDefined: boolean;
  createdAt: Date;
}

interface PaymentMethod {
  id: number;
  name: string;
  userDefined: boolean;
  createdAt: Date;
}

interface Expense {
  id: number;
  date: Date;
  category: Category;
  amount: number;
  description?: string;
  paymentMethod: PaymentMethod;
  createdAt: Date;
  updatedAt: Date;
}

interface ExpenseFilters {
  dateFrom?: Date;
  dateTo?: Date;
  categoryId?: number;
  paymentMethodId?: number;
  searchQuery?: string;
}
```

---

## Component Architecture

### React Component Hierarchy

```
App
├── Router
│   ├── DashboardPage
│   │   ├── ExpenseSummaryCards
│   │   ├── ExpenseList
│   │   └── CategoryBreakdownChart
│   ├── ExpensesPage
│   │   ├── ExpenseFilterBar
│   │   ├── ExpenseTable
│   │   └── AddEditExpenseModal
│   ├── CategoriesPage
│   │   └── CategoryManager
│   └── SettingsPage
│       └── ThemeSettings
├── providers/
│   ├── DatabaseProvider
│   ├── ExpenseProvider (Context)
│   └── ThemeProvider
└── layouts/
    └── MainLayout (Header + Navigation)
```

### Key Components

#### DatabaseProvider
- Initializes SQLite database on app start
- Provides database connection context
- Handles migrations

#### ExpenseProvider (Context)
- Central state for expenses
- CRUD operations (getExpenses, addExpense, updateExpense, deleteExpense)
- Filtering and sorting logic
- Persistence layer

#### ExpenseForm
- Controlled component for add/edit
- Form validation
- Submit handlers

#### ExpenseTable
- Paginated virtualized list (for large datasets)
- Sortable columns
- Row actions (edit, delete)

---

## Service Layer

### Database Service

```typescript
// database.ts
class DatabaseService {
  private db: Database | null = null;
  
  async initialize(): Promise<void> {
    // Open database, run migrations
  }
  
  async runMigrations(): Promise<void> {
    // Apply schema version migrations
  }
  
  getConnection(): Database {
    if (!this.db) throw new Error('Database not initialized');
    return this.db;
  }
}

// expenseRepository.ts
class ExpenseRepository {
  constructor(private dbService: DatabaseService) {}
  
  async getAll(filters?: ExpenseFilters): Promise<Expense[]> { /* */ }
  async getById(id: number): Promise<Expense | undefined> { /* */ }
  async create(expense: CreateExpenseDTO): Promise<number> { /* */ }
  async update(id: number, expense: UpdateExpenseDTO): Promise<void> { /* */ }
  async delete(id: number): Promise<void> { /* */ }
}
```

---

## State Management

### React Context Pattern

```typescript
interface ExpenseContextValue {
  expenses: Expense[];
  loading: boolean;
  error?: string;
  filters: ExpenseFilters;
  loadExpenses: (filters?: ExpenseFilters) => Promise<void>;
  addExpense: (expense: Omit<Expense, 'id' | 'createdAt' | 'updatedAt'>) => Promise<void>;
  updateExpense: (id: number, expense: Partial<Expense>) => Promise<void>;
  deleteExpense: (id: number) => Promise<void>;
  setFilters: (filters: ExpenseFilters) => void;
}

const ExpenseContext = createContext<ExpenseContextValue | null>(null);
```

### State Flow

1. **Database Changes** → Repository methods update SQLite
2. **Repository → Context** → Context methods call repository, update local state
3. **Context → Components** → Components re-render with new state
4. **User Action → Context methods** → Trigger database and state updates

---

## Architecture Constraints

### 1. Local-First Design
- All data stored locally in SQLite
- No server required for basic functionality
- Optional cloud sync in future phase

### 2. Offline Support
- Service worker caches application shell
- Database queries work offline
- Graceful degradation for unsupported features

### 3. Performance
- Database queries use indexed lookups
- List virtualization for long expense lists
- Memoization for expensive computations (e.g., category totals)

### 4. Testability
- Database service can be mocked
- Repository layer isolated for unit tests
- Components testable with React Testing Library

---

## Security Considerations

1. **Data Privacy**
   - No data transmitted without explicit user action
   - All data stored locally, never in cloud
   - Optional encryption at rest (future enhancement)

2. **Input Validation**
   - Client-side validation for UX
   - Server-side (database) validation as backup
   - Parameterized queries to prevent SQL injection

---

## Scalability Plan

### Phase 1 (Current)
- Single database file
- Simple query patterns
- No pagination needed for typical use case (< 1000 expenses)

### Future Enhancements
- Database indexing by date for time-series queries
- Pagination for expense list
- Background sync for multi-device access
- Data compression for large datasets

---

## Deployment Architecture

```
User's Device
├── Static Files (HTML/CSS/JS) - served by Vite preview or any static server
├── SQLite Database - stored in browser storage (IndexedDB/file system access)
└── Service Worker - caches assets for offline access
```

### Build Output
- Optimized JavaScript bundle (~200-500KB gzipped)
- Pre-built SQLite WASM (if using sql.js)
- Service worker for offline caching

---

## Non-Functional Requirements Alignment

| Requirement | Implementation |
|-------------|---------------|
| Performance (≤2s load) | Vite HMR, code splitting, pre-built SQLite |
| Accessibility (WCAG 2.1 AA) | Semantic HTML, ARIA labels, keyboard nav |
| Offline Support | Service worker, local SQLite storage |
| Security (Privacy) | No data transmission, local encryption option |
| Compatibility | Modern browsers via Babel/Vite polyfill configuration |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| SQLite WASM bundle size | Tree-shake unused APIs, lazy-load features |
| Database concurrency | Use read-write locks, serialize operations |
| Large dataset performance | Implement virtualized lists, pagination |
| Browser compatibility | Use sql.js instead of better-sqlite3 for web |
| State consistency | Single source of truth in Context + database |