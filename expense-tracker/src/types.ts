/**
 * Expense Tracker - Type Definitions
 * Data models for the Expense Tracker application
 */

export interface Category {
  id: number;
  name: string;
  userDefined: boolean;
  createdAt: Date;
}

export interface PaymentMethod {
  id: number;
  name: string;
  userDefined: boolean;
  createdAt: Date;
}

export interface Expense {
  id: number;
  date: Date;
  category: Category;
  amount: number;
  description?: string;
  paymentMethod: PaymentMethod;
  createdAt: Date;
  updatedAt: Date;
}

export interface CreateExpenseDTO {
  date: string;           // ISO 8601 date string
  categoryId: number;     // Foreign key to categories table
  amount: number;       // Must be > 0
  description?: string;   // Optional
  paymentMethodId: number; // Foreign key to payment_methods table
}

export interface UpdateExpenseDTO {
  date?: string;
  categoryId?: number;
  amount?: number;
  description?: string;
  paymentMethodId?: number;
}