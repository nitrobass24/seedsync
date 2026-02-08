import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

import { Notification, NotificationLevel } from '../../models/notification';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private notifications: Notification[] = [];
  private readonly notificationsSubject = new BehaviorSubject<Notification[]>(
    [],
  );

  readonly notifications$: Observable<Notification[]> =
    this.notificationsSubject.asObservable();

  show(notification: Notification): void {
    const exists = this.notifications.some(
      (n) => n.level === notification.level && n.text === notification.text,
    );
    if (!exists) {
      this.notifications = [...this.notifications, notification].sort(
        this.comparator,
      );
      this.notificationsSubject.next(this.notifications);
    }
  }

  hide(notification: Notification): void {
    const index = this.notifications.findIndex(
      (n) => n.level === notification.level && n.text === notification.text,
    );
    if (index >= 0) {
      this.notifications = [
        ...this.notifications.slice(0, index),
        ...this.notifications.slice(index + 1),
      ];
      this.notificationsSubject.next(this.notifications);
    }
  }

  private readonly comparator = (a: Notification, b: Notification): number => {
    const priorities: Record<NotificationLevel, number> = {
      [NotificationLevel.DANGER]: 0,
      [NotificationLevel.WARNING]: 1,
      [NotificationLevel.INFO]: 2,
      [NotificationLevel.SUCCESS]: 3,
    };

    if (a.level !== b.level) {
      const diff = priorities[a.level] - priorities[b.level];
      if (diff !== 0) return diff;
    }
    return b.timestamp - a.timestamp;
  };
}
