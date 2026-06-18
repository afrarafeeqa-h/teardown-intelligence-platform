import { Component } from '@angular/core';
import { EmailService } from '../services/email.service';

@Component({
  selector: 'app-email-test',
  templateUrl: './email-test.component.html'
})
export class EmailTestComponent {

  email = '';
  message = '';
  service = new EmailService();

  sendTestOtp() {
    const otp = Math.floor(100000 + Math.random() * 900000).toString();

    this.service.sendOtpEmail(this.email, otp)
      .then(() => {
        this.message = '✅ OTP sent to email successfully';
        console.log('OTP:', otp); // fallback
      })
      .catch((err) => {
        console.error(err);
        this.message = '❌ Email failed. Check console.';
      });
  }
}