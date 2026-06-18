import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { LoginComponent } from './auth/login/login.component';
import { DataUploadComponent } from './data-upload/data-upload.component';
import { AuditHistoryComponent } from './audit-history/audit-history.component';
import { DatasetTableComponent } from './dataset-table/dataset-table.component';
import { DashboardComponent } from './dashboard/dashboard.component';
import { MyUploadsComponent } from './my-uploads/my-uploads.component';
import { HostListener } from '@angular/core';

import { AuthGuard } from './guards/auth.guard';
import { AdminGuard } from './guards/admin.guard';
import { EmailTestComponent } from './email-test/email-test.component';
import { AiAssistantComponent } from './ai-assistant/ai-assistant.component';

const routes: Routes = [
  { path: 'login', component: LoginComponent },

  {
    path: 'upload',
    component: DataUploadComponent,
    canActivate: [AuthGuard]
  },

  {
  path: 'dataset',
  component: DatasetTableComponent,
  canActivate: [AuthGuard]
},

  {
    path: 'audits',
    component: AuditHistoryComponent,
    canActivate: [AuthGuard, AdminGuard]
  },
  { path: 'dashboard', 
    component: DashboardComponent },

  { path: 'my-uploads', component: MyUploadsComponent },
  {
  path: 'email-test',
  component: EmailTestComponent
},
{ path: 'ai', component: AiAssistantComponent},
  
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { path: '**', redirectTo: 'login' }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule {}