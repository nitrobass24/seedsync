import { describe, it, expect } from "vitest";
import { NotificationService } from "./notification.service";
import { Notification, NotificationLevel } from "../../models/notification";

function makeNotification(
  level: NotificationLevel,
  text: string,
  timestamp: number = Date.now(),
  dismissible: boolean = false,
): Notification {
  return { level, text, timestamp, dismissible };
}

describe("NotificationService", () => {
  let service: NotificationService;

  beforeEach(() => {
    service = new NotificationService();
  });

  it("should emit empty array initially", () => {
    let result: Notification[] | undefined;
    service.notifications$.subscribe((n) => (result = n));
    expect(result).toEqual([]);
  });

  it("should add notification and emit via notifications$", () => {
    const notification = makeNotification(NotificationLevel.INFO, "test message", 1000);
    service.show(notification);

    let result: Notification[] | undefined;
    service.notifications$.subscribe((n) => (result = n));
    expect(result).toEqual([notification]);
  });

  it("should deduplicate by level and text", () => {
    const n1 = makeNotification(NotificationLevel.INFO, "duplicate", 1000);
    const n2 = makeNotification(NotificationLevel.INFO, "duplicate", 2000);
    service.show(n1);
    service.show(n2);

    let result: Notification[] | undefined;
    service.notifications$.subscribe((n) => (result = n));
    expect(result!.length).toBe(1);
    expect(result![0]).toEqual(n1);
  });

  it("should sort by priority (DANGER first, SUCCESS last)", () => {
    const success = makeNotification(NotificationLevel.SUCCESS, "s", 1000);
    const info = makeNotification(NotificationLevel.INFO, "i", 1000);
    const warning = makeNotification(NotificationLevel.WARNING, "w", 1000);
    const danger = makeNotification(NotificationLevel.DANGER, "d", 1000);

    service.show(success);
    service.show(info);
    service.show(warning);
    service.show(danger);

    let result: Notification[] | undefined;
    service.notifications$.subscribe((n) => (result = n));
    expect(result!.map((n) => n.level)).toEqual([
      NotificationLevel.DANGER,
      NotificationLevel.WARNING,
      NotificationLevel.INFO,
      NotificationLevel.SUCCESS,
    ]);
  });

  it("should sort by timestamp descending within same priority", () => {
    const older = makeNotification(NotificationLevel.INFO, "older", 1000);
    const newer = makeNotification(NotificationLevel.INFO, "newer", 2000);
    service.show(older);
    service.show(newer);

    let result: Notification[] | undefined;
    service.notifications$.subscribe((n) => (result = n));
    expect(result!.map((n) => n.text)).toEqual(["newer", "older"]);
  });

  it("should remove matching notification on hide()", () => {
    const n1 = makeNotification(NotificationLevel.INFO, "keep", 1000);
    const n2 = makeNotification(NotificationLevel.WARNING, "remove", 2000);
    service.show(n1);
    service.show(n2);
    service.hide(n2);

    let result: Notification[] | undefined;
    service.notifications$.subscribe((n) => (result = n));
    expect(result).toEqual([n1]);
  });

  it("should be a no-op when hiding non-existent notification", () => {
    const n1 = makeNotification(NotificationLevel.INFO, "exists", 1000);
    const nonExistent = makeNotification(NotificationLevel.DANGER, "ghost", 2000);
    service.show(n1);

    let emitCount = 0;
    service.notifications$.subscribe(() => emitCount++);
    const countBefore = emitCount;
    service.hide(nonExistent);

    let result: Notification[] | undefined;
    service.notifications$.subscribe((n) => (result = n));
    expect(result).toEqual([n1]);
    expect(emitCount).toBe(countBefore);
  });
});
