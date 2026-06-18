import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { NgChartsModule } from 'ng2-charts';

import { AppComponent } from './app.component';
import { AppRoutingModule } from './app-routing.module';
import { LoginComponent } from './auth/login/login.component';
import { DataUploadComponent } from './data-upload/data-upload.component';
import { AuditHistoryComponent } from './audit-history/audit-history.component';
import { DatasetTableComponent } from './dataset-table/dataset-table.component';
import { DashboardComponent } from './dashboard/dashboard.component';
import { MyUploadsComponent } from './my-uploads/my-uploads.component';
import { EmailTestComponent } from './email-test/email-test.component';
import { AiAssistantComponent } from './ai-assistant/ai-assistant.component';

@NgModule({
  declarations: [
    AppComponent,
    LoginComponent,
    DataUploadComponent,
    AuditHistoryComponent,
    DatasetTableComponent,
    DashboardComponent,
    MyUploadsComponent,
    EmailTestComponent,
    AiAssistantComponent
  ],
  imports: [
    BrowserModule,
    NgChartsModule,
    AppRoutingModule,
    FormsModule,          //REQUIRED for ngModel
    HttpClientModule      //REQUIRED for API calls
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule {}