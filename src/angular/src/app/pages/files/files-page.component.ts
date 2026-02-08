import { Component } from '@angular/core';

import { FileOptionsComponent } from './file-options.component';
import { FileListComponent } from './file-list.component';

@Component({
  selector: 'app-files-page',
  standalone: true,
  imports: [FileOptionsComponent, FileListComponent],
  template: `
    <app-file-options></app-file-options>
    <app-file-list></app-file-list>
  `
})
export class FilesPageComponent {}
