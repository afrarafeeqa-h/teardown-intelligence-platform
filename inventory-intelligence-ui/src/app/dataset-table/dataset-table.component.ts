import { Component, OnInit, ViewEncapsulation } from '@angular/core';
import { DataService } from '../services/data.service';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-dataset-table',
  templateUrl: './dataset-table.component.html',
  styleUrls: ['./dataset-table.component.css'],
  encapsulation: ViewEncapsulation.None
})
export class DatasetTableComponent implements OnInit {

  records: any[] = [];
  columns: string[] = [];
  hasUploaded = false;
  aiInsights: string = '';
  anomalyGroups: any[] = [];
  showFilter = false;
  selectedColumn = '';
  filterValue = '';
  sortColumn = '';
  sortColumns: string[] = [];
  sortOrder = 'asc';
  filteredRecords: any[] | null = null;
  filterColumns: string[] = [];
  searchText: string = '';
  uploadedFileName: string = '';
  activeCategory: string = '';
  visibleColumns: string[] = [];
  selectedColumns: string[] = [];
  showColumnSelector: boolean = false;
  selectedStatus: string = '';
  selectedAnomaly: boolean = false;
  selectedNormal: boolean = false;
  constructor(private dataService: DataService, private http: HttpClient, private route: ActivatedRoute) {}

  ngOnInit() {
    this.hasUploaded = localStorage.getItem('hasUploaded') === 'true';
    const loadFromSaved = localStorage.getItem('loadFromSaved') === 'true';
    if (this.hasUploaded) {
      if (loadFromSaved) {
      this.loadSavedState();   //ONLY for old dataset
    } else {
      this.loadRecords();      //for new upload
    }
    this.uploadedFileName = localStorage.getItem('uploadedFileName') || '';
  }
this.route.queryParams.subscribe(params => {
  this.selectedStatus = params['status'] || '';
  this.selectedAnomaly = params['anomaly'] === 'true';
  this.selectedNormal = params['normal'] === 'true';
});
}

  //CORRECT: Only fetch data here
loadRecords() {
  this.visibleColumns = [...this.columns];
  const uploadId = localStorage.getItem('activeUploadId');

  if (!uploadId) return;

  this.http
    .get(`http://127.0.0.1:8000/data/teardown/records/editable?upload_id=${uploadId}`)
    .subscribe((res: any) => {

      this.records = res.records || [];

      if (this.records.length > 0) {
        this.columns = Object.keys(this.records[0].data);
        console.log("Columns:", this.columns);
        console.log("Records:", this.records);
        this.setFilterColumns();
        this.setSortColumns();
      }
      // ✅ CASE 1: KPI CLICK
if (this.selectedStatus) {

  this.runQualityCheck();

  setTimeout(() => {
    this.filterByStatus(this.selectedStatus);
  }, 300);
}
if (this.selectedAnomaly) {
  this.runAnomalyDetection();
}
if (this.selectedNormal) {
  this.runAnomalyDetection();
}
    });
}
  //NEW: Upload happens HERE
  uploadFile(event: any) {
  const file = event.target.files[0];
  this.uploadedFileName = file.name;  //store original file name
  localStorage.setItem('uploadedFileName', file.name);
  console.log("Uploaded file:", this.uploadedFileName);
  this.dataService.uploadTeardownCSV(file).subscribe((res: any) => {
    
    console.log("UPLOAD RESPONSE:", res);

    if (res && res.upload_id) {
      localStorage.setItem('activeUploadId', res.upload_id);
      localStorage.setItem('hasUploaded', 'true');
      localStorage.removeItem('loadFromSaved');   //IMPORTANT

      this.hasUploaded = true;

      setTimeout(() => {   //IMPORTANT FIX
        this.loadRecords();
      }, 300);             // small delay
    }
  });
}

  //Keep edit UI working
  editRow(row: any) {
    if (row.anomaly) {
      alert("Anomalous records should be reviewed, not edited directly.");
      return;
    }
    row.editing = true;
  }

  saveRow(row: any) {

  this.dataService.updateRecord(row).subscribe(() => {

    row.editing = false;

    //reload fresh data
    this.loadRecords();

    //AUTO RUN DQ
    this.runQualityCheck();

  });
}

  deleteRow(row: any) {

  const confirmed = confirm("Delete this row?");
  if (!confirmed) return;

  this.dataService.deleteRecordById(row._id)
    .subscribe(() => {

      //remove locally + reload
      this.records = this.records.filter(r => r._id !== row._id);

      this.loadRecords();   //refresh from DB
      //AUTO RUN DQ
      this.runQualityCheck();
    });
}
  runQualityCheck() {
  const uploadId = localStorage.getItem('activeUploadId');
  if (!uploadId) return;
  this.http.get(`http://127.0.0.1:8000/data/teardown/records/quality-check?upload_id=${uploadId}`).subscribe((res: any) => {
      res.records.forEach((qcRow: any) => {
        const row = this.records.find(r => r._id === qcRow._id);

        if (row) {
          row.quality_status = qcRow.quality_status;
          row.issues = qcRow.issues;
        }
      });

    });
}
runAnomalyDetection() {
  console.log("ANOMALY CLICKED");

  const uploadId = localStorage.getItem('activeUploadId');
  if (!uploadId) return;

  this.http
    .get<any>(`http://127.0.0.1:8000/data/teardown/records/anomaly-check?upload_id=${uploadId}`)
    .subscribe(res => {

      res.records.forEach((aRow: any) => {
        const row = this.records.find(r => r._id === aRow._id);

        if (row) {
          row.anomaly = aRow.anomaly;
          row.anomaly_score = aRow.anomaly_score;
          row.anomaly_reason = aRow.anomaly_reason;
        }
      });
      //IMPORTANT ADD THIS
      this.loadAnomalyGroups();
if (this.selectedAnomaly) {
        this.filteredRecords = this.records.filter(r => r.anomaly === true);
      }
if (this.selectedNormal) {
  this.filteredRecords = this.records.filter(r => r.anomaly === false);
}
    });
}

 exportCSV(event: any) {
  const option = event.target.value;
  const uploadId = localStorage.getItem('activeUploadId');

  if (option === 'clean') {
    window.open(`http://127.0.0.1:8000/data/export/clean?upload_id=${uploadId}`);
  } else if (option === 'full') {
    window.open(`http://127.0.0.1:8000/data/export/full/csv?upload_id=${uploadId}`);
  }

  //RESET dropdown
  event.target.value = "";
}

  exportExcel(event: any) {
  const option = event.target.value;
  const uploadId = localStorage.getItem('activeUploadId');

  if (option === 'clean') {
    window.open(`http://127.0.0.1:8000/data/export/clean/excel?upload_id=${uploadId}`);
  }
  else if (option === 'full') {
    window.open(`http://127.0.0.1:8000/data/export/full/excel?upload_id=${uploadId}`);
  }
  //RESET dropdown
  event.target.value = "";
}

  exportPDF(event: any) {
  const option = event.target.value;
  const uploadId = localStorage.getItem('activeUploadId');

  if (option === 'clean') {
    window.open(`http://127.0.0.1:8000/data/export/clean/pdf?upload_id=${uploadId}`);
  }
  else if (option === 'full') {
    window.open(`http://127.0.0.1:8000/data/export/full/pdf?upload_id=${uploadId}`);
  }
  //RESET dropdown
  event.target.value = "";
}
saveState() {
  const uploadId = localStorage.getItem("activeUploadId");

  this.http.post(`http://127.0.0.1:8000/save-state`, {
    upload_id: uploadId,
    records: this.records
  }).subscribe(() => {
    alert("✅ State saved");
  });
}
loadSavedState() {
  const uploadId = localStorage.getItem('activeUploadId');

  this.http
    .get(`http://127.0.0.1:8000/load-state?upload_id=${uploadId}`)
    .subscribe((res: any) => {

      if (res && res.records && res.records.length > 0) {
        this.records = res.records;
        this.columns = Object.keys(this.records[0].data);
      } else {
        // fallback to original
        this.loadRecords();
      }
    });
}
loadAnomalyGroups() {
  const uploadId = localStorage.getItem('activeUploadId');
  if (!uploadId) return;

  this.http
    .get<any>(`http://127.0.0.1:8000/analytics/anomalies-by-group?upload_id=${uploadId}`)
    .subscribe(res => {
      this.anomalyGroups = res.data.sort((a: any, b: any) => b.count - a.count) || [];
    });
}
setFilterColumns() {
  if (!this.records.length) return;

  this.filterColumns = this.columns.filter(col => {
    const values = this.records
      .map(r => r.data[col])
      .filter(v => v !== null && v !== undefined && v !== '');

    if (!values.length) return false;

    const uniqueValues = new Set(values).size;
    const total = values.length;

    // ✅ numeric column detection (safe)
    const numericCount = values.filter(v => !isNaN(parseFloat(v))).length;
    const isMostlyNumeric = numericCount / total > 0.8;

    // ✅ high uniqueness = ID-like column
    const isHighCardinality = uniqueValues / total > 0.9;

    // ✅ FINAL RULES (NO HARDCODE)
    return (
      !isMostlyNumeric &&     // remove numeric fields
      !isHighCardinality &&   // remove ID-like fields
      uniqueValues > 1        // remove constant columns
    );
  });
  console.log("Filter Columns:", this.filterColumns);
}
setSortColumns() {
  if (!this.records.length) return;

  this.sortColumns = this.columns.filter(col => {
    const sampleValues = this.records
      .map(r => r.data[col])
      .filter(v => v !== null && v !== undefined);

    if (sampleValues.length === 0) return false;

    //only numeric columns
    return sampleValues.some(v => !isNaN(parseFloat(v)));
  });

  //include anomaly_score
  this.sortColumns.push('anomaly_score');
}
toggleFilter() {
  this.showFilter = !this.showFilter;
}
applyFilter() {
  this.filteredRecords = null;
  // ✅ Reset anomaly selection when using manual filter
  this.activeCategory = '';

  // ✅ If no inputs → show all data
  if (!this.selectedColumn && !this.filterValue && !this.searchText) {
    this.filteredRecords = null;
    return;
  }

  let data = [...this.records];
  // ✅ COLUMN FILTER (SAFE)
if (this.selectedColumns.length && this.filterValue) {

  // ✅ split input into multiple values
  const values = this.filterValue
    .split(',')
    .map(v => v.trim().toLowerCase())
    .filter(v => v);

  
data = data.filter(r =>
  values.every(v =>                       //ALL values must match
    this.selectedColumns.some(col => {   //in ANY selected column
      const cellValue = r.data[col];
      return cellValue &&
        String(cellValue).toLowerCase().includes(v);
    })
  )
);
}

  // ✅ SEARCH
  if (this.searchText) {
    data = data.filter(r =>
      Object.values(r.data).some(val =>
        val && String(val).toLowerCase().includes(this.searchText.toLowerCase())
      )
    );
  }

  // ✅ SORT
  if (this.sortColumn) {
    data.sort((a, b) => {
      let valA = this.sortColumn === 'anomaly_score'
        ? a.anomaly_score
        : a.data[this.sortColumn];

      let valB = this.sortColumn === 'anomaly_score'
        ? b.anomaly_score
        : b.data[this.sortColumn];

      const numA = parseFloat(valA);
      const numB = parseFloat(valB);

      if (!isNaN(numA) && !isNaN(numB)) {
        return this.sortOrder === 'asc' ? numA - numB : numB - numA;
      } else {
        return this.sortOrder === 'asc'
          ? String(valA).localeCompare(String(valB))
          : String(valB).localeCompare(String(valA));
      }
    });
  }

  // ✅ APPLY RESULT
  this.filteredRecords = data;
}
resetFilter() {
  this.filteredRecords = null;
  this.selectedColumn = '';
  this.filterValue = '';
  this.searchText = '';
  this.sortColumn = '';
  this.activeCategory = '';
  this.selectedColumns = [];
}
exportCurrentViewCSV() {
  const dataToExport = this.filteredRecords !== null
    ? this.filteredRecords
    : this.records;

  if (!dataToExport.length) return;

  const headers = Object.keys(dataToExport[0].data);
  const rows = dataToExport.map(row =>
    headers.map(h => row.data[h] ?? '').join(',')
  );

  const csvContent = [headers.join(','), ...rows].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  const baseName = this.uploadedFileName ? this.uploadedFileName.replace('.csv', '') : 'dataset';
  link.download = baseName + '_filtered_dataset.csv';
  link.click();
}
sortByColumn(col: string) {
  if (this.sortColumn === col) {
    this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
  } else {
    this.sortColumn = col;
    this.sortOrder = 'asc';
  }
  this.applyFilter();
}
filterByCategory(category: string) {

  let detectedColumn = ''; 
if (this.activeCategory === category) {
    this.activeCategory = '';
    this.filteredRecords = null;
    return;
  }
  this.activeCategory = category;
  // ✅ Detect which column contains this category
  if (this.records.length > 0) {
    const sampleRow = this.records[0].data;

    Object.keys(sampleRow).forEach(col => {
      const match = this.records.some(r => {
        const val = r.data[col];
        return val &&
          String(val).trim().toLowerCase() === category.trim().toLowerCase();
      });

      if (match) {
        detectedColumn = col;
      }
    });
  }

  console.log("Detected column:", detectedColumn);

  // ✅ Apply filter
  let data = this.records.filter(r => {
    const value = r.data[detectedColumn];

    return value &&
      String(value).trim().toLowerCase() === category.trim().toLowerCase();
  });

  this.filteredRecords = data;
  this.activeCategory = category;

  // ✅ sync UI dynamically
  this.selectedColumn = detectedColumn;
  this.filterValue = category;
}
resetAll() {
  this.filteredRecords = null;
  this.selectedColumn = '';
  this.filterValue = '';
  this.searchText = '';
  this.sortColumn = '';
  this.activeCategory = '';
  this.selectedColumns = [];
  this.selectedStatus = '';
  this.selectedAnomaly = false;
  this.selectedNormal = false;
  console.log("All filters cleared");
}
toggleColumn(col: string, event: any) {
  if (event.target.checked) {
    if (!this.selectedColumns.includes(col)) {
      this.selectedColumns.push(col);
    }
  } else {
    this.selectedColumns = this.selectedColumns.filter(c => c !== col);
  }
}
filterByStatus(status: string) {
  this.filteredRecords = this.records.filter(r => {
    if (!r.quality_status) return false;
    return r.quality_status.toLowerCase() === status.toLowerCase();
  });
}
filterByAnomaly() {
  this.filteredRecords = this.records.filter(r => r.anomaly === true);
}
}