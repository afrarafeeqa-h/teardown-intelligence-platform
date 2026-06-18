import emailjs from '@emailjs/browser';

export class EmailService {

  sendOtpEmail(email: string, otp: string): Promise<any> {
    return emailjs.send(
      'service_3j7knok',
      'template_ro64e4z',
      {
        to_email: email,
        otp: otp
      },
      'ff4ez850Pn8UXwE1W'
    );
  }
}