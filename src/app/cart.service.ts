import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class CartService {

  private cartItems: any[] = [];
  toastMessage: string = '';

  addToCart(item: any) {
    const existing = this.cartItems.find(i => i.id === item.id);

    if (existing) {
      existing.quantity = item.quantity || 1;
    } else {
      this.cartItems.push({
        id: item.id,
        name: item.name,
        price: item.price,
        quantity: item.quantity || 1
      });
    }
  }

  getCartItems() {
    return this.cartItems;
  }

  removeItem(id: number) {
    this.cartItems = this.cartItems.filter(item => item.id !== id);
  }

  clearCart() {
    this.cartItems = [];
  }

  getItemById(id: number) {
    return this.cartItems.find(item => item.id === id);
  }

  setToast(message: string) {
    this.toastMessage = message;

    setTimeout(() => {
      this.toastMessage = '';
    }, 4000);
  }

  getCount() {
  return this.cartItems.reduce(
    (total, item) => total + item.quantity,
    0
  );
}
}