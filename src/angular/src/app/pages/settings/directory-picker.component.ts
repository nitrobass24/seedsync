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
  /** False until some path has listed, so Select never emits an unverified path. */
  loaded = false;
  errorMessage: string | null = null;

  ngOnInit(): void {
    this.currentPath = this.initialPath() || '/';
    this.load(this.currentPath, { fallBackToParent: true });
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

  /** @param fallBackToParent Initial load only: if the configured path no longer
   * exists (renamed, now a file), walk up its ancestors to the first one that
   * lists, keeping the original error visible, so the picker isn't a dead end.
   * Connection-level failures stop immediately: each remote step is a fresh
   * SSH login, and retrying one that just failed is what the lockout avoids. */
  private load(path: string, options?: { fallBackToParent?: boolean; keepError?: string }): void {
    this.loading = true;
    this.errorMessage = options?.keepError ?? null;
    const browse$ =
      this.kind() === 'local' ? this.browserService.browseLocal(path) : this.browserService.browseRemote(path);
    browse$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((result) => {
      this.loading = false;
      if (result.success) {
        this.loaded = true;
        this.currentPath = result.path ?? path;
        this.parentPath = result.parent;
        this.directories = result.directories;
      } else {
        const error = options?.keepError ?? result.errorMessage;
        const parent = options?.fallBackToParent && result.badPath ? parentPathOf(path) : null;
        if (parent !== null) {
          this.load(parent, { fallBackToParent: true, keepError: error ?? undefined });
          return;
        }
        this.errorMessage = error;
      }
      this.cdr.markForCheck();
    });
  }
}

/** POSIX dirname, or null at "/". A path with no slash (e.g. "~") falls back to "/". */
function parentPathOf(path: string): string | null {
  const trimmed = path.replace(/\/+$/, '');
  if (trimmed === '') {
    return null;
  }
  const slash = trimmed.lastIndexOf('/');
  return slash <= 0 ? '/' : trimmed.slice(0, slash);
}
