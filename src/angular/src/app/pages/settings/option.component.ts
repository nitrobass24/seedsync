import { Component, ChangeDetectionStrategy, OnInit, OnDestroy, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription, debounceTime, distinctUntilChanged } from 'rxjs';

export enum OptionType {
  Text,
  Checkbox,
  Password,
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

  readonly changeEvent = output<any>();

  readonly OptionType = OptionType;

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
    this.newValue.next(value);
  }
}
