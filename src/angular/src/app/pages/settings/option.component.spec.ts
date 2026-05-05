import '@angular/compiler';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { TestBed } from '@angular/core/testing';
import { ComponentFixture } from '@angular/core/testing';

import { OptionComponent, OptionType, OptionValue } from './option.component';
import { REDACTED_SENTINEL } from '../../models/config';

/**
 * Test the debounce/distinctUntilChanged pipe logic directly using the same
 * operators as OptionComponent, avoiding Angular component lifecycle timing issues.
 */
describe('OptionComponent — debounce pipe logic', () => {
  const DEBOUNCE_TIME_MS = 1000;
  let newValue: Subject<OptionValue>;
  let emitted: OptionValue[];
  let subscription: Subscription;

  beforeEach(() => {
    vi.useFakeTimers();
    newValue = new Subject<OptionValue>();
    emitted = [];
    subscription = newValue
      .pipe(debounceTime(DEBOUNCE_TIME_MS), distinctUntilChanged())
      .subscribe((val) => emitted.push(val));
  });

  afterEach(() => {
    subscription.unsubscribe();
    vi.useRealTimers();
  });

  it('should emit value after 1000ms debounce, not immediately', () => {
    newValue.next('hello');
    expect(emitted).toEqual([]);

    vi.advanceTimersByTime(1000);
    expect(emitted).toEqual(['hello']);
  });

  it('should emit only the final value when rapid changes occur', () => {
    newValue.next('a');
    vi.advanceTimersByTime(200);
    newValue.next('b');
    vi.advanceTimersByTime(200);
    newValue.next('c');

    expect(emitted).toEqual([]);

    vi.advanceTimersByTime(1000);
    expect(emitted).toEqual(['c']);
  });

  it('should not re-emit same value after full debounce period (distinctUntilChanged)', () => {
    newValue.next('same');
    vi.advanceTimersByTime(1000);
    expect(emitted).toEqual(['same']);

    newValue.next('same');
    vi.advanceTimersByTime(1000);
    expect(emitted).toEqual(['same']);
  });

  it('should emit different values after each debounce period', () => {
    newValue.next('first');
    vi.advanceTimersByTime(1000);
    newValue.next('second');
    vi.advanceTimersByTime(1000);

    expect(emitted).toEqual(['first', 'second']);
  });
});

/**
 * Test the onChange guard logic (password REDACTED_SENTINEL suppression)
 * and effectiveChoices computed signal.
 */
describe('OptionComponent — onChange and effectiveChoices', () => {
  let component: OptionComponent;
  let fixture: ComponentFixture<OptionComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    fixture = TestBed.createComponent(OptionComponent);
    component = fixture.componentInstance;
  });

  // Restore real timers after every test so a failing assertion inside a
  // useFakeTimers() block can't leak fake timers into the next test.
  afterEach(() => {
    vi.useRealTimers();
  });

  it('should suppress REDACTED_SENTINEL for password type', () => {
    vi.useFakeTimers();
    fixture.componentRef.setInput('type', OptionType.Password);
    fixture.detectChanges();

    // Spy on the internal Subject to verify nothing gets pushed
    const nextSpy = vi.spyOn((component as unknown as { newValue: Subject<OptionValue> }).newValue, 'next');
    component.onChange(REDACTED_SENTINEL);
    expect(nextSpy).not.toHaveBeenCalled();
  });

  it('should pass real password value through to Subject', () => {
    vi.useFakeTimers();
    fixture.componentRef.setInput('type', OptionType.Password);
    fixture.detectChanges();

    const nextSpy = vi.spyOn((component as unknown as { newValue: Subject<OptionValue> }).newValue, 'next');
    component.onChange('real-password');
    expect(nextSpy).toHaveBeenCalledWith('real-password');
  });

  it('should not suppress REDACTED_SENTINEL for non-password types', () => {
    vi.useFakeTimers();
    fixture.componentRef.setInput('type', OptionType.Text);
    fixture.detectChanges();

    const nextSpy = vi.spyOn((component as unknown as { newValue: Subject<OptionValue> }).newValue, 'next');
    component.onChange(REDACTED_SENTINEL);
    expect(nextSpy).toHaveBeenCalledWith(REDACTED_SENTINEL);
  });

  it('should include current value in choices if not in predefined list', () => {
    fixture.componentRef.setInput('choices', ['opt1', 'opt2']);
    fixture.componentRef.setInput('value', 'custom');
    fixture.detectChanges();

    expect(component.effectiveChoices()).toEqual(['custom', 'opt1', 'opt2']);
  });

  it('should not duplicate current value if already in choices', () => {
    fixture.componentRef.setInput('choices', ['opt1', 'opt2']);
    fixture.componentRef.setInput('value', 'opt1');
    fixture.detectChanges();

    expect(component.effectiveChoices()).toEqual(['opt1', 'opt2']);
  });
});
