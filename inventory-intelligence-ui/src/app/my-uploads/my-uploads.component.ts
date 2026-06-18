import { Component, OnInit } from '@angular/core';
import { DataService } from '../services/data.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-my-uploads',
  templateUrl: './my-uploads.component.html',
  styleUrls: ['./my-uploads.component.css']
})
export class MyUploadsComponent implements OnInit {

  uploads: any[] = [];
  loading = true;
  errorMsg = '';

  constructor(
    private dataService: DataService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadMyUploads();
  }

  loadMyUploads() {
    this.dataService.getMyUploads().subscribe({
      next: (res: any[]) => {
        this.uploads = res;
        this.loading = false;
      },
      error: () => {
        this.errorMsg = 'Failed to load uploads';
        this.loading = false;
      }
    });
  }

  viewUpload(uploadId: string) {
    // store selected upload
    localStorage.setItem('activeUploadId', uploadId);

    // go to dashboard
    this.router.navigate(['/dashboard']);
  }
  viewDataset(uploadId: string) {
  localStorage.setItem('activeUploadId', uploadId);
  localStorage.setItem('hasUploaded', 'true');
  localStorage.setItem('loadFromSaved', 'true');   //IMPORTANT

  this.router.navigate(['/dataset']);
}
}