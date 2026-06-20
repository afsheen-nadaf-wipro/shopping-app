import { Injectable } from '@angular/core';

export interface CartItem {
  id: number;
  name: string;
  price: number;
  stock: number;
  quantity: number;
}

@Injectable({ providedIn: 'root' })
export class CartService {
  private readonly STORAGE_KEY = 'cart_items';
  private cartItems: CartItem[] = this.loadFromStorage();
  toastMessage = '';

  // ── Read ──────────────────────────────────────────────────────────────────

  getCartItems(): CartItem[] {
    return [...this.cartItems];
  }

  getItemById(id: number): CartItem | undefined {
    return this.cartItems.find(item => item.id === id);
  }

  getCount(): number {
    return this.cartItems.reduce((sum, item) => sum + item.quantity, 0);
  }

  getTotal(): number {
    return this.cartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);
  }

  // ── Write ─────────────────────────────────────────────────────────────────

  addItem(product: { id: number; name: string; price: number; stock: number }): void {
    const existing = this.cartItems.find(i => i.id === product.id);
    if (existing) {
      if (existing.quantity < product.stock) {
        existing.quantity++;
        this.persist();
      }
      return;
    }
    if (product.stock > 0) {
      this.cartItems.push({ ...product, quantity: 1 });
      this.persist();
    }
  }

  increaseItem(id: number): boolean {
    const item = this.cartItems.find(i => i.id === id);
    if (!item) return false;
    if (item.quantity >= item.stock) return false;
    item.quantity++;
    this.persist();
    return true;
  }

  decreaseItem(id: number): void {
    const item = this.cartItems.find(i => i.id === id);
    if (!item) return;
    if (item.quantity <= 1) {
      this.removeItem(id);
      return;
    }
    item.quantity--;
    this.persist();
  }

  removeItem(id: number): void {
    this.cartItems = this.cartItems.filter(item => item.id !== id);
    this.persist();
  }

  clearCart(): void {
    this.cartItems = [];
    this.persist();
  }

  // ── Toast ─────────────────────────────────────────────────────────────────

  setToast(message: string): void {
    this.toastMessage = message;
    setTimeout(() => { this.toastMessage = ''; }, 3000);
  }

  // ── Storage ───────────────────────────────────────────────────────────────

  private persist(): void {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.cartItems));
    } catch { /* storage unavailable */ }
  }

  private loadFromStorage(): CartItem[] {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }
}
