import { Component, ChangeDetectionStrategy, ChangeDetectorRef, OnInit, inject } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';

import { ViewFileOptionsService } from '../../services/files/view-file-options.service';
import { ViewFileOptions, SortMethod } from '../../models/view-file-options';
import { ViewFile, ViewFileStatus } from '../../models/view-file';
import { ViewFileService } from '../../services/files/view-file.service';
import { DomService } from '../../services/utils/dom.service';

@Component({
  selector: 'app-file-options',
  standalone: true,
  imports: [AsyncPipe, FormsModule],
  templateUrl: './file-options.component.html',
  styleUrls: ['./file-options.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class FileOptionsComponent implements OnInit {
  ViewFileStatus = ViewFileStatus;
  SortMethod = SortMethod;

  options: Observable<ViewFileOptions>;
  headerHeight: Observable<number>;

  isExtractedStatusEnabled = false;
  isExtractingStatusEnabled = false;
  isDownloadedStatusEnabled = false;
  isDownloadingStatusEnabled = false;
  isQueuedStatusEnabled = false;
  isStoppedStatusEnabled = false;

  private _latestOptions!: ViewFileOptions;

  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly viewFileOptionsService = inject(ViewFileOptionsService);
  private readonly viewFileService = inject(ViewFileService);
  private readonly domService = inject(DomService);

  constructor() {
    this.options = this.viewFileOptionsService.options$;
    this.headerHeight = this.domService.headerHeight$;
  }

  ngOnInit(): void {
    this.viewFileService.files$.subscribe(files => {
      this.isExtractedStatusEnabled = FileOptionsComponent.isStatusEnabled(
        files, ViewFileStatus.EXTRACTED
      );
      this.isExtractingStatusEnabled = FileOptionsComponent.isStatusEnabled(
        files, ViewFileStatus.EXTRACTING
      );
      this.isDownloadedStatusEnabled = FileOptionsComponent.isStatusEnabled(
        files, ViewFileStatus.DOWNLOADED
      );
      this.isDownloadingStatusEnabled = FileOptionsComponent.isStatusEnabled(
        files, ViewFileStatus.DOWNLOADING
      );
      this.isQueuedStatusEnabled = FileOptionsComponent.isStatusEnabled(
        files, ViewFileStatus.QUEUED
      );
      this.isStoppedStatusEnabled = FileOptionsComponent.isStatusEnabled(
        files, ViewFileStatus.STOPPED
      );
      this.changeDetector.detectChanges();
    });

    this.viewFileOptionsService.options$.subscribe(options => this._latestOptions = options);
  }

  onFilterByName(name: string): void {
    this.viewFileOptionsService.setNameFilter(name);
  }

  onFilterByStatus(status: ViewFileStatus | null): void {
    this.viewFileOptionsService.setSelectedStatusFilter(status);
  }

  onSort(sortMethod: SortMethod): void {
    this.viewFileOptionsService.setSortMethod(sortMethod);
  }

  onToggleShowDetails(): void {
    this.viewFileOptionsService.setShowDetails(!this._latestOptions.showDetails);
  }

  onTogglePinFilter(): void {
    this.viewFileOptionsService.setPinFilter(!this._latestOptions.pinFilter);
  }

  private static isStatusEnabled(files: ViewFile[], status: ViewFileStatus): boolean {
    return files.findIndex(f => f.status === status) >= 0;
  }
}
