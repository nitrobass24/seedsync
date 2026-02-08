export interface Notification {
  level: NotificationLevel;
  text: string;
  timestamp: number;
  dismissible: boolean;
}

export enum NotificationLevel {
  SUCCESS = 'success',
  INFO    = 'info',
  WARNING = 'warning',
  DANGER  = 'danger',
}

export function createNotification(
  level: NotificationLevel,
  text: string,
  dismissible: boolean = false,
): Notification {
  return {
    level,
    text,
    timestamp: Date.now(),
    dismissible,
  };
}
