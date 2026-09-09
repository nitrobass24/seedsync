import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { BulkActionBarComponent } from './bulk-action-bar.component';
import { FileAction } from '../../models/file-action';

describe('BulkActionBarComponent', () => {
  let fixture: ComponentFixture<BulkActionBarComponent>;
  let component: BulkActionBarComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [BulkActionBarComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(BulkActionBarComponent);
    fixture.componentRef.setInput('count', 3);
    fixture.detectChanges();
    component = fixture.componentInstance;
  });

  function findButtonByText(text: string): HTMLButtonElement {
    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('button'),
    ) as HTMLButtonElement[];
    const btn = buttons.find((el) => el.textContent?.includes(text));
    expect(btn).toBeTruthy();
    return btn!;
  }

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should display the selection count', () => {
    const el: HTMLElement = fixture.nativeElement;
    const countSpan = el.querySelector('.count')!;
    expect(countSpan.textContent).toContain('3 selected');
  });

  it('should update displayed count when input changes', () => {
    fixture.componentRef.setInput('count', 7);
    fixture.detectChanges();

    const el: HTMLElement = fixture.nativeElement;
    const countSpan = el.querySelector('.count')!;
    expect(countSpan.textContent).toContain('7 selected');
  });

  it('should emit QUEUE when Queue button is clicked', () => {
    let emitted: FileAction | null = null;
    component.actionEvent.subscribe((a) => (emitted = a));

    const btn = findButtonByText('Queue');
    btn.click();

    expect(emitted).toBe(FileAction.QUEUE);
  });

  it('should emit STOP when Stop button is clicked', () => {
    let emitted: FileAction | null = null;
    component.actionEvent.subscribe((a) => (emitted = a));

    const btn = findButtonByText('Stop');
    btn.click();

    expect(emitted).toBe(FileAction.STOP);
  });

  it('should emit DELETE_LOCAL only on the second Delete Local click', () => {
    const emitted: FileAction[] = [];
    component.actionEvent.subscribe((a) => emitted.push(a));

    // First click arms the confirm, does NOT emit
    findButtonByText('Delete Local').click();
    expect(emitted).toEqual([]);

    // Second click emits
    fixture.detectChanges();
    findButtonByText('Confirm?').click();
    expect(emitted).toEqual([FileAction.DELETE_LOCAL]);
  });

  it('should emit DELETE_REMOTE only on the second Delete Remote click', () => {
    const emitted: FileAction[] = [];
    component.actionEvent.subscribe((a) => emitted.push(a));

    // First click arms the confirm, does NOT emit
    findButtonByText('Delete Remote').click();
    expect(emitted).toEqual([]);

    // Second click emits
    fixture.detectChanges();
    findButtonByText('Confirm?').click();
    expect(emitted).toEqual([FileAction.DELETE_REMOTE]);
  });

  it('should emit clearEvent when Clear button is clicked', () => {
    let emitted = false;
    component.clearEvent.subscribe(() => (emitted = true));

    const btn = findButtonByText('Clear');
    btn.click();

    expect(emitted).toBe(true);
  });

  it('should render exactly five buttons', () => {
    const buttons = fixture.nativeElement.querySelectorAll('button');
    expect(buttons.length).toBe(5);
  });
});

describe('BulkActionBarComponent inline bulk delete confirmation', () => {
  let fixture: ComponentFixture<BulkActionBarComponent>;
  let component: BulkActionBarComponent;

  beforeEach(async () => {
    vi.useFakeTimers();

    await TestBed.configureTestingModule({
      imports: [BulkActionBarComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(BulkActionBarComponent);
    fixture.componentRef.setInput('count', 3);
    fixture.detectChanges();
    component = fixture.componentInstance;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function findButtonByText(text: string): HTMLButtonElement {
    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('button'),
    ) as HTMLButtonElement[];
    const btn = buttons.find((el) => el.textContent?.includes(text));
    expect(btn).toBeTruthy();
    return btn!;
  }

  it('first click on Delete Local sets confirming state and does not emit', () => {
    const spy = vi.spyOn(component.actionEvent, 'emit');

    component.onDeleteLocal();

    expect(component.confirmingDelete).toBe('local');
    expect(spy).not.toHaveBeenCalled();
  });

  it('second click on Delete Local emits event and clears state', () => {
    const spy = vi.spyOn(component.actionEvent, 'emit');

    component.onDeleteLocal();
    expect(component.confirmingDelete).toBe('local');

    component.onDeleteLocal();
    expect(component.confirmingDelete).toBeNull();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('first click on Delete Remote sets confirming state and does not emit', () => {
    const spy = vi.spyOn(component.actionEvent, 'emit');

    component.onDeleteRemote();

    expect(component.confirmingDelete).toBe('remote');
    expect(spy).not.toHaveBeenCalled();
  });

  it('second click on Delete Remote emits event and clears state', () => {
    const spy = vi.spyOn(component.actionEvent, 'emit');

    component.onDeleteRemote();
    expect(component.confirmingDelete).toBe('remote');

    component.onDeleteRemote();
    expect(component.confirmingDelete).toBeNull();
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('confirming state auto-resets after 3 seconds', () => {
    component.onDeleteLocal();
    expect(component.confirmingDelete).toBe('local');

    vi.advanceTimersByTime(3000);
    expect(component.confirmingDelete).toBeNull();
  });

  it('clicking Delete Local while confirming remote switches to local', () => {
    component.onDeleteRemote();
    expect(component.confirmingDelete).toBe('remote');

    component.onDeleteLocal();
    expect(component.confirmingDelete).toBe('local');
  });

  it("button label switches to 'Confirm?' after first Delete Local click", () => {
    // Drive through a real DOM click so OnPush marks the view dirty.
    findButtonByText('Delete Local').click();
    fixture.detectChanges();

    expect(component.confirmingDelete).toBe('local');
    const btn = findButtonByText('Confirm?');
    expect(btn.textContent).toContain('Confirm?');
  });

  it('ngOnDestroy clears the confirm timer so no reset fires', () => {
    component.onDeleteLocal();
    expect(component.confirmingDelete).toBe('local');

    component.ngOnDestroy();
    vi.advanceTimersByTime(5000);

    // State stays as-is (timer was cleared, no reset happened)
    expect(component.confirmingDelete).toBe('local');
  });
});
