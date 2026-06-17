import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent {

  email: string = '';
  password: string = '';
  message: string = '';

  constructor(private router: Router) {}

  onLogin() {
    if (this.email === 'admin@example.com' && this.password === '123456') {
      this.message = 'Login successful!';
      this.router.navigate(['/items']); // ✅ redirect
    } else {
      this.message = 'Invalid credentials';
    }
  }
}
