import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { BulkActionBarComponent } from './bulk-action-bar.component';

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

  it('should emit queueEvent when Queue button is clicked', () => {
    let emitted = false;
    component.queueEvent.subscribe(() => (emitted = true));

    const btn = findButtonByText('Queue');
    btn.click();

    expect(emitted).toBe(true);
  });

  it('should emit stopEvent when Stop button is clicked', () => {
    let emitted = false;
    component.stopEvent.subscribe(() => (emitted = true));

    const btn = findButtonByText('Stop');
    btn.click();

    expect(emitted).toBe(true);
  });

  it('should emit deleteLocalEvent when Delete Local button is clicked', () => {
    let emitted = false;
    component.deleteLocalEvent.subscribe(() => (emitted = true));

    const btn = findButtonByText('Delete Local');
    btn.click();

    expect(emitted).toBe(true);
  });

  it('should emit deleteRemoteEvent when Delete Remote button is clicked', () => {
    let emitted = false;
    component.deleteRemoteEvent.subscribe(() => (emitted = true));

    const btn = findButtonByText('Delete Remote');
    btn.click();

    expect(emitted).toBe(true);
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
