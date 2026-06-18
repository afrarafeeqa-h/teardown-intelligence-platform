import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-ai-assistant',
  templateUrl: './ai-assistant.component.html',
  styleUrls: ['./ai-assistant.component.css']
})
export class AiAssistantComponent implements OnInit {
   userQuery = '';
   chatReply = '';
   aiInsights: string = '';
   predictiveAI: string = '';
   fixSuggestions: string = '';
   forecastAI: string = '';   // cleaner naming
   loadingAI = false;
   active: string = '';
  constructor(private http: HttpClient) {}

  ngOnInit(): void {
  }
  getForecastAI() {
  const uploadId = localStorage.getItem('activeUploadId');

  this.loadingAI = true;

  this.http.get(`http://127.0.0.1:8000/genai/forecast?upload_id=${uploadId}`)
    .subscribe({
      next: (res: any) => {
        this.forecastAI = res.reply.replace(/\*/g, '');
        this.loadingAI = false;
      },
      error: (err) => {
        console.error(err);
        this.loadingAI = false;
      }
    });
}
getPredictive() {
  const uploadId = localStorage.getItem('activeUploadId');

  this.loadingAI = true;

  this.http.get(`http://127.0.0.1:8000/genai/predictive?upload_id=${uploadId}`)
    .subscribe({
      next: (res: any) => {
        this.predictiveAI = res.reply.replace(/\*/g, '');
        this.loadingAI = false;
      },
      error: (err) => {
        console.error(err);
        this.loadingAI = false;
      }
    });
}
getFixSuggestions() {
  const uploadId = localStorage.getItem('activeUploadId');

  this.loadingAI = true;

  this.http.get(`http://127.0.0.1:8000/genai/fix?upload_id=${uploadId}`)
    .subscribe({
      next: (res: any) => {
        this.fixSuggestions = res.reply.replace(/\*/g, '');
        this.loadingAI = false;
      },
      error: (err) => {
        console.error(err);
        this.loadingAI = false;
      }
    });
}
generateAI() {
  const uploadId = localStorage.getItem('activeUploadId');

  this.loadingAI = true;

  this.http.get(`http://127.0.0.1:8000/genai/insights?upload_id=${uploadId}`)
    .subscribe({
      next: (res: any) => {
        this.aiInsights = res.reply.replace(/\*/g, '');
        this.loadingAI = false;
      },
      error: (err) => {
        console.error(err);
        this.loadingAI = false;
      }
    });
}
askAI() {
  const uploadId = localStorage.getItem('activeUploadId');

  this.loadingAI = true;

  this.http.post('http://127.0.0.1:8000/genai/chat', {
    query: this.userQuery,
    upload_id: uploadId   //CRITICAL
  }).subscribe({
    next: (res: any) => {
      this.chatReply = res.reply.replace(/\*/g, '');
      this.loadingAI = false;
    },
    error: (err) => {
      console.error(err);
      this.loadingAI = false;
    }
  });
}
}