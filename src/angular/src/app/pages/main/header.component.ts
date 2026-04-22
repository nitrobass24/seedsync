import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { Observable } from 'rxjs';

import { LoggerService } from '../../services/utils/logger.service';
import { ServerStatusService } from '../../services/server/server-status.service';
import { ServerStatus } from '../../models/server-status';
import { Notification, NotificationLevel, createNotification } from '../../models/notification';
import { NotificationService } from '../../services/utils/notification.service';
import { Localization } from '../../models/localization';

interface NotificationRule {
  key: string;
  shouldShow: (status: ServerStatus) => boolean;
  level: (status: ServerStatus) => NotificationLevel;
  text: (status: ServerStatus) => string;
}

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HeaderComponent implements OnInit {
  public NotificationLevel = NotificationLevel;

  public notifications$: Observable<Notification[]>;

  private readonly _logger = inject(LoggerService);
  private readonly _serverStatusService = inject(ServerStatusService);
  private readonly _notificationService = inject(NotificationService);
  private readonly _destroyRef = inject(DestroyRef);

  private _activeNotifications = new Map<string, Notification>();

  private readonly _rules: NotificationRule[] = [
    {
      key: 'server',
      shouldShow: status => !status.server.up,
      level: () => NotificationLevel.DANGER,
      text: status => status.server.errorMessage ?? '',
    },
    {
      key: 'waitingForRemoteScan',
      shouldShow: status =>
        status.server.up && status.controller.latestRemoteScanTime == null && !status.controller.noEnabledPairs,
      level: () => NotificationLevel.INFO,
      text: () => Localization.Notification.STATUS_REMOTE_SCAN_WAITING,
    },
    {
      key: 'remoteServerError',
      shouldShow: status =>
        status.server.up && status.controller.latestRemoteScanFailed === true && !status.controller.noEnabledPairs,
      level: () => NotificationLevel.WARNING,
      text: status => Localization.Notification.STATUS_REMOTE_SERVER_ERROR(
        status.controller.latestRemoteScanError ?? ''
      ),
    },
    {
      key: 'noEnabledPairs',
      shouldShow: status => status.server.up && status.controller.noEnabledPairs,
      level: () => NotificationLevel.WARNING,
      text: () => Localization.Notification.STATUS_NO_ENABLED_PAIRS,
    },
  ];

  constructor() {
    this.notifications$ = this._notificationService.notifications$;
  }

  public dismiss(notif: Notification) {
    this._notificationService.hide(notif);
  }

  ngOnInit() {
    this._serverStatusService.status$.pipe(
      takeUntilDestroyed(this._destroyRef),
    ).subscribe({
      next: status => {
        for (const rule of this._rules) {
          this._applyRule(rule, status);
        }
      }
    });
  }

  private _applyRule(rule: NotificationRule, status: ServerStatus): void {
    const prev = this._activeNotifications.get(rule.key) ?? null;

    if (rule.shouldShow(status)) {
      const text = rule.text(status);
      if (prev != null && prev.text === text) {
        return;
      }
      if (prev != null) {
        this._notificationService.hide(prev);
      }
      const notification = createNotification(rule.level(status), text);
      this._activeNotifications.set(rule.key, notification);
      this._notificationService.show(notification);
      if (rule.key === 'server') {
        this._logger.debug('New server notification: %O', notification);
      }
    } else {
      if (prev != null) {
        this._notificationService.hide(prev);
        this._activeNotifications.delete(rule.key);
      }
    }
  }
}
