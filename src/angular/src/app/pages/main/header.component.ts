import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Observable } from 'rxjs';

import { LoggerService } from '../../services/utils/logger.service';
import { ServerStatusService } from '../../services/server/server-status.service';
import { Notification, NotificationLevel, createNotification } from '../../models/notification';
import { NotificationService } from '../../services/utils/notification.service';
import { Localization } from '../../models/localization';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss']
})
export class HeaderComponent implements OnInit {
  public NotificationLevel = NotificationLevel;

  public notifications$: Observable<Notification[]>;

  private readonly _logger = inject(LoggerService);
  private readonly _serverStatusService = inject(ServerStatusService);
  private readonly _notificationService = inject(NotificationService);

  private _prevServerNotification: Notification | null = null;
  private _prevWaitingForRemoteScanNotification: Notification | null = null;
  private _prevRemoteServerErrorNotification: Notification | null = null;

  constructor() {
    this.notifications$ = this._notificationService.notifications$;
  }

  public dismiss(notif: Notification) {
    this._notificationService.hide(notif);
  }

  ngOnInit() {
    // Set up a subscriber to show server status notifications
    this._serverStatusService.status$.subscribe({
      next: status => {
        if (status.server.up) {
          if (this._prevServerNotification != null) {
            this._notificationService.hide(this._prevServerNotification);
            this._prevServerNotification = null;
          }
        } else {
          const notification = createNotification(
            NotificationLevel.DANGER,
            status.server.errorMessage ?? ''
          );
          if (
            this._prevServerNotification == null ||
            this._prevServerNotification.text !== notification.text
          ) {
            if (this._prevServerNotification != null) {
              this._notificationService.hide(this._prevServerNotification);
            }
            this._prevServerNotification = notification;
            this._notificationService.show(this._prevServerNotification);
            this._logger.debug('New server notification: %O', this._prevServerNotification);
          }
        }
      }
    });

    // Set up a subscriber to show waiting for remote scan notification
    this._serverStatusService.status$.subscribe({
      next: status => {
        if (status.server.up && status.controller.latestRemoteScanTime == null) {
          if (this._prevWaitingForRemoteScanNotification == null) {
            this._prevWaitingForRemoteScanNotification = createNotification(
              NotificationLevel.INFO,
              Localization.Notification.STATUS_REMOTE_SCAN_WAITING
            );
            this._notificationService.show(this._prevWaitingForRemoteScanNotification);
          }
        } else {
          if (this._prevWaitingForRemoteScanNotification != null) {
            this._notificationService.hide(this._prevWaitingForRemoteScanNotification);
            this._prevWaitingForRemoteScanNotification = null;
          }
        }
      }
    });

    // Set up a subscriber to show remote server error notifications
    this._serverStatusService.status$.subscribe({
      next: status => {
        if (status.server.up && status.controller.latestRemoteScanFailed === true) {
          const level = NotificationLevel.WARNING;
          const text = Localization.Notification.STATUS_REMOTE_SERVER_ERROR(
            status.controller.latestRemoteScanError ?? ''
          );
          if (this._prevRemoteServerErrorNotification != null
            && this._prevRemoteServerErrorNotification.text !== text) {
            this._notificationService.hide(this._prevRemoteServerErrorNotification);
            this._prevRemoteServerErrorNotification = null;
          }
          if (this._prevRemoteServerErrorNotification == null) {
            this._prevRemoteServerErrorNotification = createNotification(level, text);
            this._notificationService.show(this._prevRemoteServerErrorNotification);
          }
        } else {
          if (this._prevRemoteServerErrorNotification != null) {
            this._notificationService.hide(this._prevRemoteServerErrorNotification);
            this._prevRemoteServerErrorNotification = null;
          }
        }
      }
    });
  }
}
