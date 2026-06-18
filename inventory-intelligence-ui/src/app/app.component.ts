import { Component, OnInit } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html'
})
export class AppComponent implements OnInit {

  isLoggedIn = false;
  isLoginPage = false;
  isAdmin = false;

  constructor(private router: Router) {}

  ngOnInit(): void {
    this.router.events.subscribe(event => {
      if (event instanceof NavigationEnd) {

        // ✅ Detect login page
        this.isLoginPage = event.urlAfterRedirects === '/login';

        // ✅ Auth state
        const token = localStorage.getItem('token');
        const role = localStorage.getItem('role');

        this.isLoggedIn = !!token && !this.isLoginPage;
        this.isAdmin = role === 'ADMIN';
      }
    });
  }

  logout(): void {
    localStorage.clear();
    this.isLoggedIn = false;
    this.isAdmin = false;
    this.router.navigate(['/login']);
  }
  showDropdown = false;
userEmail = localStorage.getItem('userEmail');

toggleDropdown() {
  this.showDropdown = !this.showDropdown;
}

goToProfile() {
  alert('Profile:\n' + this.userEmail);
}

showActivity() {
  alert('Recent Activity:\n- Uploaded dataset\n- Viewed dashboard');
}
}