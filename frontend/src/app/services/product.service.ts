import { Injectable } from '@angular/core';
import { Observable, of, tap } from 'rxjs';
import { map } from 'rxjs/operators';
import { ApiService } from './api.service';
import { Product, ProductsResponse } from '../models/product.model';

@Injectable({ providedIn: 'root' })
export class ProductService {
  private cachedProducts: Product[] | null = null;

  constructor(private api: ApiService) {}

  getProducts(): Observable<Product[]> {
    if (this.cachedProducts) {
      return of(this.cachedProducts);
    }
    return this.api.get<ProductsResponse>('/products').pipe(
      map(response => response.products),
      tap(products => { this.cachedProducts = products; })
    );
  }

  clearCache(): void {
    this.cachedProducts = null;
  }
}
