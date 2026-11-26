/**
 * Expense Tracker - Main Entry Point
 * Application entry point for the expense tracking system
 */

import { DatabaseService } from './database';
import { ExpenseRepository } from './expenseRepository';

// Initialize the application
async function main() {
  const dbService = new DatabaseService();
  await dbService.initialize();

  const expenseRepo = new ExpenseRepository(dbService);

  console.log('Expense Tracker initialized successfully');

  // Example usage
  const expenseId = await expenseRepo.create({
    date: '2026-11-25',
    categoryId: 1,
    amount: 100.50,
    description: 'Sample expense',
    paymentMethodId: 1,
  });

  console.log(`Created expense with ID: ${expenseId}`);
}

main().catch(console.error);