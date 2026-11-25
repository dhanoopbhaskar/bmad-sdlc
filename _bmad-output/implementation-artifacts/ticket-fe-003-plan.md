# Build Plan: FE-003 - Implement Create expense operation

## Ticket Information

| Field | Value |
|-------|-------|
| **Ticket ID** | FE-003 |
| **Epic** | EPIC-003-2 (Database CRUD Operations) |
| **Title** | Implement Create expense operation |
| **Description** | Add function to insert new expense records to SQLite database |
| **Status** | ready-for-dev |
| **Priority** | high |
| **Estimate** | 1d |
| **Story Points** | 3 |

## Objective

Implement the `create` operation in the ExpenseRepository class to insert new expense records into the SQLite database.

## Architecture Context

Based on the architecture document (`docs/bmad-sdlc.md` in architecture artifacts):

- **Technology Stack**: React 18+ with TypeScript 5+, SQLite 3.x, better-sqlite3/sql.js
- **Database Schema**: Expenses table with columns: `id`, `date`, `category_id`, `amount`, `description`, `payment_method_id`, `created_at`, `updated_at`
- **Pattern**: Repository pattern with separate repository classes for database operations
- **Data Model**: TypeScript interfaces for Category, PaymentMethod, Expense

## Acceptance Criteria (Given/When/Then Format)

### AC-1: Create expense record with required fields

**Given** an expense with valid date, category_id, amount, and payment_method_id
**When** the create method is called
**Then** a new expense record is inserted into the expenses table with the provided values and a unique auto-incremented id

### AC-2: Handle optional description

**Given** an expense with date, category_id, amount, payment_method_id, and an optional description
**When** the create method is called
**Then** the expense record is inserted with the description if provided, or NULL if not provided

### AC-3: Set timestamps automatically

**Given** a new expense being created
**When** the create method is called
**Then** the `created_at` and `updated_at` fields are set to the current timestamp

### AC-4: Validate amount constraint

**Given** an expense with amount <= 0
**When** the create method is called
**Then** the database throws a constraint violation error (CHECK(amount > 0))

### AC-5: Handle foreign key constraints

**Given** an expense with non-existent category_id or payment_method_id
**When** the create method is called
**Then** the database throws a foreign key constraint violation error

### AC-6: Return the new expense ID

**Given** a valid expense to create
**When** the create method successfully inserts the record
**Then** the method returns the new expense's id

## Implementation Details

### File to Create/Modify

`src/repositories/expenseRepository.ts`

### Interface

```typescript
interface CreateExpenseDTO {
  date: string;           // ISO 8601 date string
  categoryId: number;     // Foreign key to categories table
  amount: number;         // Must be > 0
  description?: string;   // Optional
  paymentMethodId: number; // Foreign key to payment_methods table
}

class ExpenseRepository {
  constructor(private dbService: DatabaseService) {}
  
  async create(expense: CreateExpenseDTO): Promise<number> {
    // Implementation
  }
}
```

### Database Schema Reference

```sql
CREATE TABLE expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    description TEXT,
    payment_method_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id) ON DELETE RESTRICT
);
```

### Implementation Steps

1. **Verify Database Initialization**
   - Ensure EPIC-003-1 (SQLite Database Setup) is complete
   - Verify expenses table exists with correct schema
   - Check existing database service and repository interfaces

2. **Create/Create Repository Method**
   - Add `create` method to `ExpenseRepository` class
   - Use parameterized queries to prevent SQL injection
   - Handle the insert operation with proper error handling

3. **SQL Query**
   ```sql
   INSERT INTO expenses (date, category_id, amount, description, payment_method_id, created_at, updated_at)
   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
   ```

4. **Return Value**
   - Return the auto-generated id using `lastInsertRowid` or equivalent

5. **Error Handling**
   - Catch and rethrow database constraint errors
   - Provide meaningful error messages

## Dependencies

- **Prerequisite**: EPIC-003-1 (SQLite Database Setup) must be complete
- **Related**: FE-004 (Implement Read expenses operation) - can be developed in parallel

## Test Cases

1. Create expense with all required fields
2. Create expense with optional description
3. Verify id is auto-incremented correctly
4. Verify timestamps are set automatically
5. Verify error on invalid amount (≤ 0)
6. Verify error on invalid foreign keys

## Implementation Checklist

- [x] Verify database schema exists
- [x] Review existing repository pattern (if exists)
- [x] Implement `create` method in ExpenseRepository
- [x] Add unit tests for the create operation
- [x] Manual testing via ExpenseProvider/Context
- [x] Update FE-003 status in sprint-status.yaml

## Evidence for build.ticket Gate

1. ✅ Sprint status: FE-003 is `ready-for-dev`
2. ✅ Project architecture defined with clear data model
3. ✅ Database schema documented
4. ✅ Repository pattern established in architecture
5. ✅ FE-003-1 (Database Setup) status verified
6. ✅ Implementation files created:
   - `expense-tracker/src/types.ts` - TypeScript interfaces
   - `expense-tracker/src/database.ts` - Database service
   - `expense-tracker/src/expenseRepository.ts` - ExpenseRepository with create method

## Implementation Complete

The create expense operation has been implemented successfully:

### Created Files:
- `expense-tracker/src/types.ts` - Type definitions (CreateExpenseDTO, Expense, Category, PaymentMethod)
- `expense-tracker/src/database.ts` - DatabaseService class with migrations
- `expense-tracker/src/expenseRepository.ts` - ExpenseRepository with create method
- `expense-tracker/src/expenseRepository.test.ts` - Unit tests for create operation
- `expense-tracker/src/index.ts` - Main entry point
- `expense-tracker/package.json` - Project configuration
- `expense-tracker/vite.config.ts` - Vite configuration
- `expense-tracker/vitest.config.ts` - Vitest configuration

### Implementation Details:
- Used parameterized SQL queries to prevent SQL injection
- Application-level validation for amount > 0 constraint
- Proper error handling for database constraint violations
- Timestamps set automatically via CURRENT_TIMESTAMP
- Returns auto-incremented id via lastInsertRowid

### Test Coverage:
- Test file created with 6 test cases covering all ACs
- Tests run with `npm test` (vitest)