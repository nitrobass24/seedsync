import {
  Component,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  DestroyRef,
  HostListener,
  OnInit,
  inject,
  input,
  output,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { DirectoryBrowserService } from '../../services/settings/directory-browser.service';

export type DirectoryBrowseKind = 'local' | 'remote';

@Component({
  selector: 'app-directory-picker',
  standalone: true,
  imports: [],
  templateUrl: './directory-picker.component.html',
  styleUrls: ['./directory-picker.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DirectoryPickerComponent implements OnInit {
  readonly kind = input.required<DirectoryBrowseKind>();
  readonly initialPath = input<string>('/');

  readonly pathSelected = output<string>();
  readonly cancelPick = output<void>();

  private readonly browserService = inject(DirectoryBrowserService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);

  currentPath = '/';
  parentPath: string | null = null;
  directories: string[] = [];
  loading = false;
  errorMessage: string | null = null;

  ngOnInit(): void {
    this.load(this.initialPath() || '/');
  }

  onEnterDirectory(name: string): void {
    const next = this.currentPath === '/' ? `/${name}` : `${this.currentPath}/${name}`;
    this.load(next);
  }

  onGoUp(): void {
    if (this.parentPath !== null) {
      this.load(this.parentPath);
    }
  }

  onSelect(): void {
    this.pathSelected.emit(this.currentPath);
  }

  onCancel(): void {
    this.cancelPick.emit();
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.onCancel();
  }

  private load(path: string): void {
    this.loading = true;
    this.errorMessage = null;
    const browse$ =
      this.kind() === 'local' ? this.browserService.browseLocal(path) : this.browserService.browseRemote(path);
    browse$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((result) => {
      this.loading = false;
      if (result.success) {
        this.currentPath = result.path ?? path;
        this.parentPath = result.parent;
        this.directories = result.directories;
      } else {
        this.errorMessage = result.errorMessage;
      }
      this.cdr.markForCheck();
    });
  }
}
