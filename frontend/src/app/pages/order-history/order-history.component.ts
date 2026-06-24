import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { finalize } from 'rxjs';
import { OrderHistoryOrder, OrderService } from '../../services/order.service';

@Component({
  selector: 'app-order-history',
  imports: [CommonModule],
  templateUrl: './order-history.component.html',
  styleUrl: './order-history.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class OrderHistoryComponent {
  private readonly orderService = inject(OrderService);

  readonly orders = signal<OrderHistoryOrder[]>([]);
  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly hasOrders = computed(() => this.orders().length > 0);

  constructor() {
    this.loadOrders();
  }

  loadOrders(): void {
    this.loading.set(true);
    this.errorMessage.set('');

    this.orderService.getMyOrders()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
      next: (response) => {
        this.orders.set(response.orders);
      },
      error: (error: unknown) => {
        console.error('Failed to load order history', error);
        this.errorMessage.set(this.getErrorMessage(error));
      }
    });
  }

  trackOrder(index: number, order: OrderHistoryOrder): number {
    return order.order_id;
  }

  private getErrorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const backendMessage = error.error?.error;
      if (typeof backendMessage === 'string' && backendMessage.trim()) {
        return backendMessage;
      }

      if (error.status === 0) {
        return 'Unable to reach the server. Please check your connection and try again.';
      }

      if (error.status === 401) {
        return 'Your session has expired. Please sign in again.';
      }
    }

    return 'We could not load your order history right now. Please try again.';
  }
}