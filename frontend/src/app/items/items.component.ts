import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { CartService } from '../cart.service';
import { ProductService } from '../services/product.service';
import { Product } from '../models/product.model';

@Component({
  selector: 'app-items',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './items.component.html',
  styleUrls: ['./items.component.css']
})
export class ItemsComponent implements OnInit, OnDestroy {
  searchText = '';
  items: Product[] = [];
  isLoading = true;
  errorMessage = '';
  readonly categories = [
    'Women\'s Fashion',
    'Handbags',
    'Jewelry',
    'Shoes',
    'Beauty',
    'Fragrance',
    'Lifestyle Accessories',
  ];

  private destroy$ = new Subject<void>();

  constructor(
    public cartService: CartService,
    private productService: ProductService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadProducts();
  }

  loadProducts(): void {
    this.isLoading = true;
    this.errorMessage = '';

    this.productService.getProducts()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (products) => {
          this.isLoading = false;
          this.items = this.syncWithCart(products);
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.isLoading = false;
          this.errorMessage = err.status === 0
            ? 'Cannot reach the server. Please check your connection.'
            : 'Failed to load products. Please try again.';
          this.cdr.markForCheck();
        }
      });
  }

  private syncWithCart(products: Product[]): Product[] {
    return products.map(product => {
      const cartItem = this.cartService.getItemById(product.id);
      return cartItem
        ? { ...product, quantity: cartItem.quantity, showQty: true }
        : { ...product, quantity: 0, showQty: false };
    });
  }

  get filteredItems(): Product[] {
    return this.items.filter(item =>
      item.name.toLowerCase().includes(this.searchText.toLowerCase())
    );
  }

  addToCart(item: Product): void {
    this.cartService.addItem(item);
    item.quantity = 1;
    item.showQty = true;
    this.cartService.setToast(`${item.name} added to your bag ✅`);
  }

  increase(item: Product): void {
    const added = this.cartService.increaseItem(item.id);
    if (added) {
      item.quantity = (item.quantity || 0) + 1;
      this.cartService.setToast(`${item.name} updated in your bag ✅`);
    } else {
      this.cartService.setToast(`⚠️ Only ${item.stock} in stock`);
    }
  }

  decrease(item: Product): void {
    if (item.quantity === 1) {
      this.cartService.removeItem(item.id);
      item.quantity = 0;
      item.showQty = false;
      this.cartService.setToast(`${item.name} removed from your bag ❌`);
    } else if (item.quantity && item.quantity > 1) {
      this.cartService.decreaseItem(item.id);
      item.quantity--;
      this.cartService.setToast(`${item.name} updated in your bag ✅`);
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}