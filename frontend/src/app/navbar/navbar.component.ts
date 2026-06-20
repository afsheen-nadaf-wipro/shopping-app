import { Component, OnInit, OnDestroy } from '@angular/core';
import { Router, NavigationEnd, RouterModule } from '@angular/router';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { CartService } from '../cart.service';
import { AuthService, AuthUser } from '../services/auth.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [RouterModule, CommonModule],
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.css']
})
export class NavbarComponent implements OnInit, OnDestroy {
  isLoginPage = false;
  currentUser: AuthUser | null = null;
  private subs = new Subscription();

  constructor(
    public cartService: CartService,
    private router: Router,
    private authService: AuthService
  ) {}

  ngOnInit(): void {
    this.subs.add(
      this.router.events.subscribe(event => {
        if (event instanceof NavigationEnd) {
          this.isLoginPage = event.url === '/' || event.url === '/login';
        }
      })
    );

    this.subs.add(
      this.authService.getCurrentUser().subscribe(user => {
        this.currentUser = user;
      })
    );
  }

  logout(): void {
    this.authService.logout();
  }

  ngOnDestroy(): void {
    this.subs.unsubscribe();
  }
}