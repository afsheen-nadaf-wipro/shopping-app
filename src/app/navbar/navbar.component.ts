import { Component } from '@angular/core';
import { Router, NavigationEnd, RouterModule } from '@angular/router';
import { CartService } from '../cart.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [RouterModule, CommonModule],
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.css']
})
export class NavbarComponent {
  isLoginPage = false;

  constructor(public cartService: CartService, private router: Router) {
    this.router.events.subscribe(event => {
      if (event instanceof NavigationEnd) {
        this.isLoginPage = event.url === '/' || event.url === '/login';
      }
    });
  }
}