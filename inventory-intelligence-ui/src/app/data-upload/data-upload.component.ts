import { Component, ViewEncapsulation } from '@angular/core';
import { DataService } from '../services/data.service';

@Component({
  selector: 'app-data-upload',
  templateUrl: './data-upload.component.html',
  styleUrls: ['./data-upload.component.css'],
  encapsulation: ViewEncapsulation.None
})
export class DataUploadComponent {

  selectedFile: File | null = null;
  message = '';

  constructor(private dataService: DataService) {}

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
  }
  
upload() {
  if (!this.selectedFile) return;
  localStorage.setItem('uploadedFileName', this.selectedFile.name);
  this.dataService.uploadTeardownCSV(this.selectedFile).subscribe({
    next: (res: any) => {
      this.message = 'Upload successful';
      localStorage.setItem('hasUploaded', 'true');
      
      //Store upload_id so dashboards & history can use it
      localStorage.setItem('activeUploadId', res.upload_id);

      console.log('Upload metadata:', res);
    },
    error: () => this.message = 'Upload failed'
  });
}
isDragOver = false;

onDragOver(event: DragEvent) {
  event.preventDefault();
  this.isDragOver = true;
}

onDrop(event: DragEvent) {
  event.preventDefault();
  this.isDragOver = false;

  if (event.dataTransfer?.files.length) {
    this.selectedFile = event.dataTransfer.files[0];
  }
}
}