import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class DataService {

  private baseUrl = 'http://127.0.0.1:8000';

  constructor(private http: HttpClient) {}

  uploadTeardownCSV(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post(
      `${this.baseUrl}/data/upload/teardown`,
      formData,
      {
        headers: {
          'X-User-Email': localStorage.getItem('userEmail') || ''
        }
      }
    );
  }

  getEditableRecords() {
    return this.http.get(`${this.baseUrl}/data/teardown/records/editable`);
  }
  getDashboardSummary() {
  return this.http.get(`${this.baseUrl}/dashboard/summary`);
}
updateRecord(record: any) {
  return this.http.put(
    `${this.baseUrl}/data/update`,
    record
  );
}
deleteRecordById(recordId: string) {
  return this.http.delete(
    `${this.baseUrl}/data/teardown/records/by-id/${recordId}`
  );
}
getMyUploads() {
  return this.http.get<any[]>('http://127.0.0.1:8000/uploads', {
    headers: {
      'X-User-Email': localStorage.getItem('userEmail') || ''
    }
  });
}
getAuditHistory() {
  return this.http.get<any[]>('http://127.0.0.1:8000/audit-history');
}
}
