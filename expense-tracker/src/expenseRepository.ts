/**
 * Expense Tracker - Expense Repository
 * Implements CRUD operations for expenses
 */

import { DatabaseService } from './database';
import { CreateExpenseDTO, UpdateExpenseDTO, Expense, Category, PaymentMethod } from './types';

export class ExpenseRepository {
  constructor(private dbService: DatabaseService) {}

  async create(expense: CreateExpenseDTO): Promise<number> {
    const db = this.dbService.getConnection();

    const stmt = db.prepare(`
      INSERT INTO expenses (date, category_id, amount, description, payment_method_id, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    `);

    // Validate amount constraint at application level
    if (expense.amount <= 0) {
      throw new Error('Amount must be greater than 0');
    }

    const info = stmt.run(
      expense.date,
      expense.categoryId,
      expense.amount,
      expense.description ?? null,
      expense.paymentMethodId
    );

    return info.lastInsertRowid as number;
  }

  async getAll(filters?: {
    dateFrom?: string;
    dateTo?: string;
    categoryId?: number;
    paymentMethodId?: number;
    searchQuery?: string;
  }): Promise<Expense[]> {
    const db = this.dbService.getConnection();

    let query = `
      SELECT e.id, e.date, e.category_id, e.amount, e.description, 
             e.payment_method_id, e.created_at, e.updated_at
      FROM expenses e
    `;

    const conditions: string[] = [];
    const params: (string | number)[] = [];

    if (filters?.dateFrom) {
      conditions.push('e.date >= ?');
      params.push(filters.dateFrom);
    }

    if (filters?.dateTo) {
      conditions.push('e.date <= ?');
      params.push(filters.dateTo);
    }

    if (filters?.categoryId !== undefined) {
      conditions.push('e.category_id = ?');
      params.push(filters.categoryId);
    }

    if (filters?.paymentMethodId !== undefined) {
      conditions.push('e.payment_method_id = ?');
      params.push(filters.paymentMethodId);
    }

    if (filters?.searchQuery) {
      conditions.push('e.description LIKE ?');
      params.push(`%${filters.searchQuery}%`);
    }

    if (conditions.length > 0) {
      query += ' WHERE ' + conditions.join(' AND ');
    }

    query += ' ORDER BY e.date DESC';

    const rows = db.prepare(query).all(...params) as any[];

    return rows.map(row => ({
      id: row.id,
      date: new Date(row.date),
      category: { id: row.category_id, name: '', userDefined: false, createdAt: new Date() },
      amount: row.amount,
      description: row.description ?? undefined,
      paymentMethod: { id: row.payment_method_id, name: '', userDefined: false, createdAt: new Date() },
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
    }));
  }

  async getById(id: number): Promise<Expense | undefined> {
    const db = this.dbService.getConnection();

    const row = db.prepare('SELECT * FROM expenses WHERE id = ?').get(id) as any;

    if (!row) return undefined;

    return {
      id: row.id,
      date: new Date(row.date),
      category: { id: row.category_id, name: '', userDefined: false, createdAt: new Date() },
      amount: row.amount,
      description: row.description ?? undefined,
      paymentMethod: { id: row.payment_method_id, name: '', userDefined: false, createdAt: new Date() },
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
    };
  }

  async update(id: number, expense: UpdateExpenseDTO): Promise<void> {
    const db = this.dbService.getConnection();

    const fields: string[] = [];
    const params: (string | number)[] = [];

    if (expense.date !== undefined) {
      fields.push('date = ?');
      params.push(expense.date);
    }

    if (expense.categoryId !== undefined) {
      fields.push('category_id = ?');
      params.push(expense.categoryId);
    }

    if (expense.amount !== undefined) {
      if (expense.amount <= 0) {
        throw new Error('Amount must be greater than 0');
      }
      fields.push('amount = ?');
      params.push(expense.amount);
    }

    if (expense.description !== undefined) {
      fields.push('description = ?');
      params.push(expense.description ?? null);
    }

    if (expense.paymentMethodId !== undefined) {
      fields.push('payment_method_id = ?');
      params.push(expense.paymentMethodId);
    }

    if (fields.length === 0) return;

    params.push(id);

    const stmt = db.prepare(`
      UPDATE expenses 
      SET ${fields.join(', ')}, updated_at = CURRENT_TIMESTAMP 
      WHERE id = ?
    `);

    stmt.run(...params);
  }

  async delete(id: number): Promise<void> {
    const db = this.dbService.getConnection();

    const stmt = db.prepare('DELETE FROM expenses WHERE id = ?');
    stmt.run(id);
  }
}