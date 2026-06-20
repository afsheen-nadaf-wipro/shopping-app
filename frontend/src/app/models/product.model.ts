export interface Product {
  id: number;
  name: string;
  description: string;
  price: number;
  stock: number;
  image_url: string;
  created_at: string;
  quantity?: number;
  showQty?: boolean;
}

export interface ProductsResponse {
  products: Product[];
}
