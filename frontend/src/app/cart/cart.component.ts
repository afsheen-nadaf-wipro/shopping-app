import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { CartService, CartItem } from '../cart.service';
import { OrderService } from '../services/order.service';

@Component({
  selector: 'app-cart',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './cart.component.html',
  styleUrls: ['./cart.component.css']
})
export class CartComponent implements OnInit {
  cartItems: CartItem[] = [];
  isCheckingOut = false;
  orderError = '';
  placedOrderId: number | null = null;

  constructor(
    public cartService: CartService,
    private orderService: OrderService,
    private cdr: ChangeDetectorRef,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.cartItems = this.cartService.getCartItems();
  }

  trackById(_: number, item: CartItem): number {
    return item.id;
  }

  increase(item: CartItem): void {
    const added = this.cartService.increaseItem(item.id);
    if (added) {
      item.quantity = this.cartService.getItemById(item.id)?.quantity ?? item.quantity;
      this.cartService.setToast(`${item.name} updated ✅`);
    } else {
      this.cartService.setToast(`⚠️ Only ${item.stock} in stock`);
    }
  }

  decrease(item: CartItem): void {
    if (item.quantity === 1) {
      this.remove(item);
    } else {
      this.cartService.decreaseItem(item.id);
      item.quantity = this.cartService.getItemById(item.id)?.quantity ?? item.quantity;
      this.cartService.setToast(`${item.name} updated ✅`);
    }
  }

  remove(item: CartItem): void {
    this.cartService.removeItem(item.id);
    this.cartItems = this.cartService.getCartItems();
    this.cartService.setToast(`${item.name} removed ❌`);
  }

  checkout(): void {
    if (this.isCheckingOut || this.cartItems.length === 0) return;

    this.isCheckingOut = true;
    this.orderError = '';

    const request = {
      items: this.cartItems.map(item => ({
        product_id: item.id,
        quantity: item.quantity
      }))
    };

    this.orderService.checkout(request).subscribe({
      next: (response) => {
        this.placedOrderId = response.order.id;
        this.cartService.clearCart();
        this.cartItems = [];
        this.isCheckingOut = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.isCheckingOut = false;
        if (err.status === 409) {
          this.orderError = err.error?.error ?? 'Some items are out of stock. Please update your cart.';
        } else if (err.status === 400) {
          this.orderError = err.error?.error ?? 'Invalid order. Please check your cart.';
        } else if (err.status === 404) {
          this.orderError = 'One or more products no longer exist. Please remove them and try again.';
        } else {
          this.orderError = 'Something went wrong. Please try again.';
        }
        this.cdr.markForCheck();
      }
    });
  }

  continueShopping(): void {
    this.router.navigate(['/items']);
  }
}