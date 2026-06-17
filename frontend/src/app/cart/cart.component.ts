import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CartService } from '../cart.service';

@Component({
  selector: 'app-cart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './cart.component.html',
  styleUrls: ['./cart.component.css']
})
export class CartComponent {

  cartItems: any[] = [];

  constructor(public cartService: CartService) {}

  ngOnInit() {
    this.cartItems = this.cartService.getCartItems();
  }

  trackById(index: number, item: any) {
    return item.id;
  }

  getTotal() {
    return this.cartItems.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0
    );
  }

  increase(item: any) {
    item.quantity++;

    this.cartService.addToCart(item);
    this.cartService.setToast(`${item.name} updated ✅`);
  }

  decrease(item: any) {
    if (item.quantity === 1) {
      this.remove(item);
    } else {
      item.quantity--;

      this.cartService.addToCart(item);
      this.cartService.setToast(`${item.name} updated ✅`);
    }
  }

  remove(item: any) {
    this.cartService.removeItem(item.id);
    this.cartItems = this.cartService.getCartItems();

    this.cartService.setToast(`${item.name} removed ❌`);
  }

  checkout() {
    this.cartService.clearCart();
    this.cartItems = [];

    this.cartService.setToast('✅ Order placed successfully!');
  }
}