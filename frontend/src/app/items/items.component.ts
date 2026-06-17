import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CartService } from '../cart.service';

type Item = {
  id: number;
  name: string;
  price: number;
  quantity?: number;
  showQty?: boolean;
};

@Component({
  selector: 'app-items',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './items.component.html',
  styleUrls: ['./items.component.css']
})
export class ItemsComponent implements OnInit {

  searchText: string = '';

  constructor(public cartService: CartService) {}

  items: Item[] = [
    { id: 1, name: 'Laptop', price: 50000 },
    { id: 2, name: 'Phone', price: 20000 },
    { id: 3, name: 'Headphones', price: 2000 },
    { id: 4, name: 'Keyboard', price: 1500 },
    { id: 5, name: 'Mouse', price: 800 }
  ];

  ngOnInit() {
    this.syncWithCart();
  }

  syncWithCart() {
    this.items.forEach(item => {
      const cartItem = this.cartService.getItemById(item.id);

      if (cartItem) {
        item.quantity = cartItem.quantity;
        item.showQty = true;
      } else {
        item.quantity = 0;
        item.showQty = false;
      }
    });
  }

  get filteredItems() {
    return this.items.filter(item =>
      item.name.toLowerCase().includes(this.searchText.toLowerCase())
    );
  }

  addToCart(item: Item) {
    item.quantity = 1;
    item.showQty = true;

    this.cartService.addToCart(item);
    this.cartService.setToast(`${item.name} added ✅`);
  }

  increase(item: Item) {
    item.quantity = (item.quantity || 0) + 1;

    this.cartService.addToCart(item);
    this.cartService.setToast(`${item.name} updated ✅`);
  }

  decrease(item: Item) {
    if (item.quantity === 1) {
      // ✅ remove item completely
      this.cartService.removeItem(item.id);

      item.quantity = 0;
      item.showQty = false;

      this.cartService.setToast(`${item.name} removed ❌`);
    } else if (item.quantity && item.quantity > 1) {
      item.quantity--;

      this.cartService.addToCart(item);
      this.cartService.setToast(`${item.name} updated ✅`);
    }
  }
}