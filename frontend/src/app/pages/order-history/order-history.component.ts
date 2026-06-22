import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Order, OrderService } from '../../services/order.service';

@Component({
  selector: 'app-order-history',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './order-history.component.html',
  styleUrl: './order-history.component.css'
})
export class OrderHistoryComponent implements OnInit {

  orders: Order[] = [];
  loading = true;
  error = '';

  constructor(private orderService: OrderService) {}

  ngOnInit(): void {
    this.getOrders();
  }

  getOrders(): void {
    this.orderService.getOrders().subscribe({
      next: (response) => {
        this.orders = response.orders;
        this.loading = false;
      },
      error: (error) => {
        console.error(error);
        this.error = 'Failed to load orders';
        this.loading = false;
      }
    });
  }
}