/**
 * Expense Tracker - Expense Repository Unit Tests
 * Tests for the create operation
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { DatabaseService } from './database';
import { ExpenseRepository } from './expenseRepository';
import { CreateExpenseDTO } from './types';

describe('ExpenseRepository', () => {
  let dbService: DatabaseService;
  let repo: ExpenseRepository;

  beforeAll(async () => {
    dbService = new DatabaseService(':memory:');
    await dbService.initialize();
    repo = new ExpenseRepository(dbService);

    // Insert test data for categories and payment methods
    const db = dbService.getConnection();
    db.prepare('INSERT INTO categories (name) VALUES (?)').run('Food');
    db.prepare('INSERT INTO categories (name) VALUES (?)').run('Transport');
    db.prepare('INSERT INTO payment_methods (name) VALUES (?)').run('Credit Card');
    db.prepare('INSERT INTO payment_methods (name) VALUES (?)').run('Cash');
  });

  afterAll(() => {
    dbService.close();
  });

  describe('create', () => {
    it('should create an expense with all required fields', async () => {
      const expense: CreateExpenseDTO = {
        date: '2026-11-25',
        categoryId: 1,
        amount: 100.50,
        paymentMethodId: 1,
      };

      const id = await repo.create(expense);

      expect(id).toBeGreaterThan(0);

      const expenseResult = await repo.getById(id);
      expect(expenseResult).toBeDefined();
      expect(expenseResult?.date).toEqual(new Date('2026-11-25'));
      expect(expenseResult?.amount).toBe(100.50);
      expect(expenseResult?.category.id).toBe(1);
      expect(expenseResult?.paymentMethod.id).toBe(1);
    });

    it('should create an expense with optional description', async () => {
      const expense: CreateExpenseDTO = {
        date: '2026-11-25',
        categoryId: 1,
        amount: 50.00,
        description: 'Dinner with family',
        paymentMethodId: 1,
      };

      const id = await repo.create(expense);

      const expenseResult = await repo.getById(id);
      expect(expenseResult?.description).toBe('Dinner with family');
    });

    it('should throw error when amount is zero', async () => {
      const expense: CreateExpenseDTO = {
        date: '2026-11-25',
        categoryId: 1,
        amount: 0,
        paymentMethodId: 1,
      };

      await expect(repo.create(expense)).rejects.toThrow('Amount must be greater than 0');
    });

    it('should throw error when amount is negative', async () => {
      const expense: CreateExpenseDTO = {
        date: '2026-11-25',
        categoryId: 1,
        amount: -50.00,
        paymentMethodId: 1,
      };

      await expect(repo.create(expense)).rejects.toThrow('Amount must be greater than 0');
    });

    it('should set created_at and updated_at timestamps', async () => {
      const expense: CreateExpenseDTO = {
        date: '2026-11-25',
        categoryId: 1,
        amount: 75.00,
        paymentMethodId: 1,
      };

      const id = await repo.create(expense);

      const expenseResult = await repo.getById(id);
      expect(expenseResult?.createdAt).toBeInstanceOf(Date);
      expect(expenseResult?.updatedAt).toBeInstanceOf(Date);
    });

    it('should generate auto-incremented id', async () => {
      const expense1: CreateExpenseDTO = {
        date: '2026-11-25',
        categoryId: 1,
        amount: 50.00,
        paymentMethodId: 1,
      };

      const expense2: CreateExpenseDTO = {
        date: '2026-11-25',
        categoryId: 2,
        amount: 75.00,
        paymentMethodId: 2,
      };

      const id1 = await repo.create(expense1);
      const id2 = await repo.create(expense2);

      expect(id2).toBeGreaterThan(id1);
    });
  });
});