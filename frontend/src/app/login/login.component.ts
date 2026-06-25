import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NgForm } from '@angular/forms';
import { finalize, switchMap } from 'rxjs';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent {
  name = '';
  email = '';
  password = '';
  confirmPassword = '';
  emailAvailabilityMessage = '';
  errorMessage = '';
  successMessage = '';
  isLoading = false;
  isCreateAccount = false;
  submitAttempted = false;

  constructor(private authService: AuthService) {}

  onSubmit(form: NgForm): void {
    this.submitAttempted = true;

    if (form.invalid) {
      this.errorMessage = 'Please complete all required fields.';
      return;
    }

    if (this.isCreateAccount) {
      this.onRegister(form);
      return;
    }

    this.onLogin(form);
  }

  toggleMode(createAccount: boolean): void {
    this.isCreateAccount = createAccount;
    this.submitAttempted = false;
    this.emailAvailabilityMessage = '';
    this.errorMessage = '';
    this.successMessage = '';
  }

  onEmailChange(): void {
    this.emailAvailabilityMessage = '';
  }

  private onLogin(form: NgForm): void {
    this.emailAvailabilityMessage = '';
    this.errorMessage = '';
    this.successMessage = '';

    const email = this.email.trim();
    const password = this.password.trim();
    if (!email || !password) {
      this.errorMessage = 'Email and password are required.';
      this.markFormTouched(form);
      return;
    }

    this.isLoading = true;

    this.authService.login({ email, password })
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
      next: () => {
        // Navigation handled inside AuthService
      },
      error: (err) => {
        if (err.status === 0) {
          this.errorMessage = 'Cannot reach the server. Please check your connection.';
        } else if (err.status === 401 || err.status === 400) {
          this.errorMessage = err.error?.error ?? 'Invalid email or password.';
        } else {
          this.errorMessage = 'An unexpected error occurred. Please try again.';
        }
      }
    });
  }

  private onRegister(form: NgForm): void {
    this.emailAvailabilityMessage = '';
    this.errorMessage = '';
    this.successMessage = '';

    const name = this.name.trim();
    const email = this.email.trim();
    const password = this.password.trim();
    const confirmPassword = this.confirmPassword.trim();

    if (!name || !email || !password || !confirmPassword) {
      this.errorMessage = 'Please fill in all required fields to create your account.';
      this.markFormTouched(form);
      return;
    }

    if (password.length < 6) {
      this.errorMessage = 'Password must be at least 6 characters.';
      return;
    }

    if (password !== confirmPassword) {
      this.errorMessage = 'Passwords do not match.';
      return;
    }

    this.isLoading = true;

    this.authService.register({
      name,
      email,
      password
    }).pipe(
      switchMap(() => this.authService.login({
        email,
        password
      })),
      finalize(() => this.isLoading = false)
    ).subscribe({
      next: () => {
        this.successMessage = 'Account created successfully.';
      },
      error: (err) => {
        if (err.status === 0) {
          this.errorMessage = 'Cannot reach the server. Please check your connection.';
        } else if (err.status === 409) {
          this.emailAvailabilityMessage = 'This email is already in use. Sign in instead or try a different email address.';
          this.errorMessage = '';
        } else if (err.status === 400) {
          this.errorMessage = err.error?.error ?? 'Please check your details and try again.';
        } else {
          this.errorMessage = 'Unable to create your account right now. Please try again.';
        }
      }
    });
  }

  private markFormTouched(form: NgForm): void {
    Object.values(form.controls).forEach((control) => control.markAsTouched());
  }
}
