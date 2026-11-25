/**
 * Expense Tracker - Database Service
 * Manages SQLite database connection and schema
 */

import Database from 'better-sqlite3';

export class DatabaseService {
  private db: Database.Database | null = null;
  private dbPath: string;

  constructor(dbPath: string = 'expense-tracker.db') {
    this.dbPath = dbPath;
  }

  async initialize(): Promise<void> {
    // Open database
    this.db = new Database(this.dbPath);
    
    // Run migrations
    await this.runMigrations();
  }

  async runMigrations(): Promise<void> {
    if (!this.db) {
      throw new Error('Database not initialized');
    }

    const migration = `
      CREATE TABLE IF NOT EXISTS categories (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          user_defined INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS payment_methods (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          user_defined INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS expenses (
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

      CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
      CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);
      CREATE INDEX IF NOT EXISTS idx_expenses_amount ON expenses(amount);
    `;

    this.db.exec(migration);
  }

  getConnection(): Database.Database {
    if (!this.db) {
      throw new Error('Database not initialized - call initialize() first');
    }
    return this.db;
  }

  close(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }
}