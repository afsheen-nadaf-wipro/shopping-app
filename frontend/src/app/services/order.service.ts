import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';

export interface CheckoutItem {
  product_id: number;
  quantity: number;
}

export interface CheckoutRequest {
  items: CheckoutItem[];
}

export interface Order {
  id: number;
  user_id: number;
  total_amount: number;
  status: string;
  created_at: string;
}

export interface CheckoutResponse {
  message: string;
  order: Order;
}

export interface OrdersResponse {
  orders: Order[];
}

@Injectable({
  providedIn: 'root'
})
export class OrderService {

  constructor(private api: ApiService) {}

  checkout(request: CheckoutRequest): Observable<CheckoutResponse> {
    return this.api.post<CheckoutResponse>(
      '/orders/checkout',
      request
    );
  }

  getOrders(): Observable<OrdersResponse> {
    return this.api.get<OrdersResponse>(
      '/orders'
    );
  }
}