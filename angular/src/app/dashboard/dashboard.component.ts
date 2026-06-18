import { Component, OnInit, NgZone } from '@angular/core';
import { DataService } from '../services/data.service';
import { ChartData, ChartType, ChartOptions } from 'chart.js';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { Router } from '@angular/router';

import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {

  hasUploaded = false;
  summary: any;
  showInsight1 = false;
  showInsight2 = false;
  showInsight3 = false;
  activeSliceIndex: number | null = null;

  // ------------------------
  // Data Quality Bar Chart
  // ------------------------
  barChartType: ChartType = 'bar';

  barChartData: ChartData<'bar'> = {
    labels: ['Clean', 'Warning', 'Rejected'],
    datasets: [
      {
        label: '',
        data: [0, 0, 0],
        backgroundColor: ['green', 'orange', 'red']
      }
    ]
  };

  barChartOptions: ChartOptions<'bar'> = {
  responsive: true,
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      callbacks: {
        label: (context: any) => {
          const value = context.raw;
          const total = this.summary?.total_records || 0;

          const percent = total
            ? ((value / total) * 100).toFixed(1)
            : '0';

          return `${value} (${percent}%)`;
        }
      }
    }
  },
  scales: {
    x: {
      title: {
        display: true,
        text: 'Validation Status'
      }
    },
    y: {
      title: {
        display: true,
        text: 'Number of Records'
      },
      beginAtZero: true
    }
  }
};

  // ------------------------
  // Anomaly Pie Chart
  // ------------------------
  anomalyChartType: 'pie' = 'pie';

  anomalyChartData: ChartData<'pie'> = {
    labels: ['Normal', 'Anomalies'],
    datasets: [
      {
        data: [0, 0],
        backgroundColor: ['#1976d2', '#d32f2f']
      }
    ]
  };
  anomalyChartOptions: ChartOptions<'pie'> = {
  responsive: true,
  plugins: {
    tooltip: {
      callbacks: {
        label: (context) => {
          const label = context.label ?? '';
          const value = context.raw as number;
          const data = context.dataset.data as number[];
          const total = data.reduce((a, b) => a + b, 0);
          const percent = total ? ((value / total) * 100).toFixed(1) : '0';
          return `${label}: ${value} (${percent}%)`;
        }
      }
    },
    legend: {
      position: 'top',
      labels: {
        usePointStyle: true
      }
    }
  },
  onClick: (_event, elements, chart) => {
    if (elements.length > 0) {
      const index = elements[0].index;
      const label = this.anomalyChartData.labels?.[index];
      
this.activeSliceIndex = index;

    // ✅ update chart style
    const meta = chart.getDatasetMeta(0);

    meta.data.forEach((slice: any, i: number) => {
      slice.offset = i === index ? 20 : 0;   // ✅ push selected slice out
    });

    chart.update();

this.ngZone.run(() => {

      if (label === 'Anomalies') {
        this.router.navigate(['/dataset'], {
          queryParams: { anomaly: true }
        });
      }

      if (label === 'Normal') {
        this.router.navigate(['/dataset'], {
          queryParams: { normal: true }   // ✅ NEW
        });
      }

    });

  }
  }
};
  riskScores: any[] = [];
  recommendations: string[] = [];
  noAnomalyData = false;

  constructor(private dataService: DataService, private http: HttpClient, private route: ActivatedRoute, private router: Router, private ngZone: NgZone) {}

  ngOnInit(): void {

  this.hasUploaded = !!localStorage.getItem('activeUploadId');

  this.route.queryParams.subscribe(params => {

    const uploadIdFromRoute = params['uploadId'];

    if (uploadIdFromRoute && uploadIdFromRoute !== 'undefined') {

      this.loadDashboardData(uploadIdFromRoute);

      localStorage.setItem('activeUploadId', uploadIdFromRoute);

    } else {

      const uploadId = localStorage.getItem('activeUploadId');

      if (uploadId) {
        this.loadDashboardData(uploadId);
      }
    }

  });

  setTimeout(() => this.showInsight1 = true, 500);
  setTimeout(() => this.showInsight2 = true, 1000);
  setTimeout(() => this.showInsight3 = true, 1500);
}
loadDashboardData(uploadId: string) {
  this.http.get(`http://127.0.0.1:8000/dashboard/summary?upload_id=${uploadId}`).subscribe((res: any) => {
    this.summary = res;
    this.barChartData.datasets[0].data = [
    res.clean_records,
    res.warning_records,
    res.rejected_records
  ];

  if (!res.anomalies || res.anomalies <= 0) {
    this.noAnomalyData = true;
  } else {
    this.noAnomalyData = false;
  }

  this.anomalyChartData = {
    labels: ['Normal', 'Anomalies'],
    datasets: [{
      data: [
        res.total_records - res.anomalies,
        res.anomalies
      ],
      backgroundColor: ['#1976d2', '#d32f2f']
    }]
  };
});
}
navigateToTable(status: string) {
  this.router.navigate(['/dataset'], {
    queryParams: { status: status }
  });
}
  downloadDashboard() {
    const element = document.getElementById('dashboard-content');

    if (!element) return;

    html2canvas(element, { scale: 2 }).then(canvas => {
      const imgData = canvas.toDataURL('image/png');

      const pdf = new jsPDF('p', 'mm', 'a4');

      const imgWidth = 210;
      const pageHeight = 295;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      while (heightLeft > 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }

      pdf.save('teardown_dashboard.pdf');
    });
  }
}