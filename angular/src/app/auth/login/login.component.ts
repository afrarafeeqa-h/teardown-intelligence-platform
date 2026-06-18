import { Component, OnInit, ViewEncapsulation} from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { EmailService } from '../../services/email.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css'],
  encapsulation: ViewEncapsulation.None
})
export class LoginComponent implements OnInit {

  email = '';
  otp = '';
  generatedOtp = '';
  otpSent = false;
  message = '';
  private emailService = new EmailService();

  constructor(
    private authService: AuthService,
    private router: Router,
  ) {}
  
  ngOnInit() {
    this.email = '';
    this.otp = '';
    this.message = '';
    this.otpSent = false;
}

  sendOtp() {
    if (this.otpSent) return;
  const otp = Math.floor(100000 + Math.random() * 900000).toString();

  this.generatedOtp = otp;

  this.emailService.sendOtpEmail(this.email, otp)
    .then(() => {
      this.otpSent = true;
      this.message = '✅ OTP sent to your email';
    })
    .catch((error) => {
      console.error(error);

      // ✅ fallback
      console.log('OTP (fallback):', otp);

      this.otpSent = true;
      this.message = '⚠️ Email failed. Check console';
    });
}

  verifyOtp() {

  if (this.otp === this.generatedOtp) {

    this.authService.verifyOtp(this.email, this.otp).subscribe((res: any) => {
      console.log("ROLE FROM BACKEND:", res.role);
      localStorage.setItem('token', res.token);
      localStorage.setItem('role', res.role);
      localStorage.setItem('userEmail', this.email);

      this.message = '✅ Login successful';

      setTimeout(() => {
        console.log("Redirecting with role:", res.role);
        console.log("Token in storage:", localStorage.getItem('token'));
        if (res.role === 'ADMIN') {
          this.router.navigate(['/audits']);
        } else {
          this.router.navigate(['/upload']);
        }
      }, 800);

    });

  } else {
    this.message = '❌ Invalid OTP';
  }
}

  logout(): void {
    localStorage.clear();
    this.router.navigate(['/login']);
}
}