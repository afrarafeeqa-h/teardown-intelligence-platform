import { Component, OnInit } from '@angular/core';
import { DataService } from '../services/data.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-audit-history',
  templateUrl: './audit-history.component.html',
  styleUrls: ['./audit-history.component.css']
})
export class AuditHistoryComponent implements OnInit {

  audits: any[] = [];

  constructor(
  private dataService: DataService,
  private router: Router
) {}
  
ngOnInit() {
  this.dataService.getAuditHistory().subscribe((res: any[]) => {
    this.audits = res;
  });
}

viewAudit(audit: any) {
  console.log("Clicked Upload ID:", audit.upload_id); //ADD
  this.router.navigate(['/dashboard'], {
    queryParams: { uploadId: audit.upload_id }
  });
}
}