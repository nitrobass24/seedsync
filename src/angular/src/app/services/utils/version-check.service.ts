import { Injectable, inject } from '@angular/core';
import { compareVersions } from 'compare-versions';

import { RestService } from './rest.service';
import { LoggerService } from './logger.service';
import { NotificationService } from './notification.service';
import { NotificationLevel, createNotification } from '../../models/notification';
import { Localization } from '../../models/localization';

import packageJson from '../../../../package.json';

@Injectable({ providedIn: 'root' })
export class VersionCheckService {
  private readonly GITHUB_LATEST_RELEASE_URL =
    'https://api.github.com/repos/nitrobass24/seedsync/releases/latest';

  private readonly restService = inject(RestService);
  private readonly notificationService = inject(NotificationService);
  private readonly logger = inject(LoggerService);

  constructor() {
    this.checkVersion();
  }

  private checkVersion(): void {
    this.restService.sendRequest(this.GITHUB_LATEST_RELEASE_URL).subscribe({
      next: (reaction) => {
        if (reaction.success) {
          let jsonResponse: any;
          let latestVersion: string;
          let url: string;
          try {
            jsonResponse = JSON.parse(reaction.data!);
            latestVersion = jsonResponse.tag_name;
            url = jsonResponse.html_url;
          } catch (e) {
            this.logger.error('Unable to parse github response: %O', e);
            return;
          }
          const message = Localization.Notification.NEW_VERSION_AVAILABLE(url);
          this.logger.debug('Latest version: ', message);
          if (isVersionNewer(latestVersion)) {
            this.notificationService.show(
              createNotification(NotificationLevel.INFO, message, true),
            );
          }
        } else {
          this.logger.warn('Unable to fetch latest version info: %O', reaction);
        }
      },
    });
  }
}

function isVersionNewer(version: string): boolean {
  // Remove the 'v' at the beginning, if any
  version = version.replace(/^v/, '');
  // Replace - with .
  version = version.replace(/-/g, '.');
  return compareVersions(version, packageJson.version) > 0;
}
