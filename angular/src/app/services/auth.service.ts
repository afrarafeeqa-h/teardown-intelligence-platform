import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root'
})
export class AuthService {

  private baseUrl = 'http://127.0.0.1:8000';

  constructor(private http: HttpClient) {}

  sendOtp(email: string) {
    return this.http.post(
      `${this.baseUrl}/auth/send-otp`,
      { email: email }
    );
  }

  verifyOtp(email: string, otp: string) {
    return this.http.post(
      `${this.baseUrl}/auth/verify-otp`,
      { 
        email: email,
        otp: otp
 }
    );
  }

getUserRole(email: string) {
  return this.http.get<any>(`http://127.0.0.1:8000/get-role?email=${email}`);
}

}