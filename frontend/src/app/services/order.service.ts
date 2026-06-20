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

export interface OrderDetail {
  id: number;
  total_amount: number;
  status: string;
  created_at: string;
}

export interface CheckoutResponse {
  message: string;
  order: OrderDetail;
}

@Injectable({ providedIn: 'root' })
export class OrderService {
  constructor(private api: ApiService) {}

  checkout(request: CheckoutRequest): Observable<CheckoutResponse> {
    return this.api.post<CheckoutResponse>('/orders/checkout', request);
  }
}
