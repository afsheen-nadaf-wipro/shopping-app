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

export interface OrderHistoryItem {
  product_name: string;
  quantity: number;
  price_at_purchase: number;
}

export interface OrderHistoryOrder {
  order_id: number;
  total_amount: number;
  status: string;
  created_at: string;
  items: OrderHistoryItem[];
}

export interface CheckoutResponse {
  message: string;
  order: Order;
}

export interface OrdersResponse {
  orders: Order[];
}

export interface OrderHistoryResponse {
  orders: OrderHistoryOrder[];
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

  getMyOrders(): Observable<OrderHistoryResponse> {
    return this.api.get<OrderHistoryResponse>(
      '/orders/my-orders'
    );
  }
}