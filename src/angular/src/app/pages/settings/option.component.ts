import { Component, ChangeDetectionStrategy, OnInit, OnDestroy, input, output, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription, debounceTime, distinctUntilChanged } from 'rxjs';

export enum OptionType {
  Text,
  Checkbox,
  Password,
  Select,
}

@Component({
  selector: 'app-option',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './option.component.html',
  styleUrls: ['./option.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OptionComponent implements OnInit, OnDestroy {
  readonly type = input<OptionType>(OptionType.Text);
  readonly label = input<string>('');
  readonly value = input<any>(null);
  readonly description = input<string | null>(null);
  readonly disabled = input<boolean>(false);
  readonly choices = input<string[]>([]);

  readonly changeEvent = output<any>();

  readonly OptionType = OptionType;

  /** Effective choices list — includes the current value if it's not in the predefined choices. */
  readonly effectiveChoices = computed(() => {
    const c = this.choices();
    const v = this.value();
    if (v != null && typeof v === 'string' && v !== '' && !c.includes(v)) {
      return [v, ...c];
    }
    return c;
  });

  private readonly DEBOUNCE_TIME_MS = 1000;
  private readonly newValue = new Subject<any>();
  private subscription?: Subscription;

  ngOnInit(): void {
    this.subscription = this.newValue
      .pipe(debounceTime(this.DEBOUNCE_TIME_MS), distinctUntilChanged())
      .subscribe({ next: (val) => this.changeEvent.emit(val) });
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }

  onChange(value: any): void {
    // Don't send updates for password fields when the value is the redacted sentinel.
    // The server returns "********" for sensitive fields; sending it back would
    // overwrite the real password with the sentinel.
    if (this.type() === OptionType.Password && value === '********') {
      return;
    }
    this.newValue.next(value);
  }
}
