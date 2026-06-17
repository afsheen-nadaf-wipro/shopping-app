import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from './navbar/navbar.component'; 
import { CartService } from './cart.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-root',
  standalone: true, 
  imports: [RouterOutlet, NavbarComponent, CommonModule], 
  templateUrl: './app.html',
  styleUrls: ['./app.css']  
})
export class App {
  protected readonly title = signal('angular-app');
  constructor(public cartService: CartService) {}
}