import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { AsyncPipe, NgTemplateOutlet } from '@angular/common';

import { LoggerService } from '../../services/utils/logger.service';
import { ConfigService } from '../../services/settings/config.service';
import { NotificationService } from '../../services/utils/notification.service';
import { ServerCommandService } from '../../services/server/server-command.service';
import { ConnectedService } from '../../services/utils/connected.service';
import { Notification, NotificationLevel, createNotification } from '../../models/notification';
import { Localization } from '../../models/localization';
import { Config } from '../../models/config';
import { ClickStopPropagationDirective } from '../../common/click-stop-propagation.directive';
import { OptionComponent } from './option.component';
import {
  IOptionsContext,
  OPTIONS_CONTEXT_SERVER,
  OPTIONS_CONTEXT_DISCOVERY,
  OPTIONS_CONTEXT_CONNECTIONS,
  OPTIONS_CONTEXT_OTHER,
  OPTIONS_CONTEXT_AUTOQUEUE,
  OPTIONS_CONTEXT_EXTRACT,
} from './options-list';

@Component({
  selector: 'app-settings-page',
  standalone: true,
  imports: [AsyncPipe, NgTemplateOutlet, OptionComponent, ClickStopPropagationDirective],
  templateUrl: './settings-page.component.html',
  styleUrls: ['./settings-page.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsPageComponent implements OnInit {
  readonly OPTIONS_CONTEXT_SERVER = OPTIONS_CONTEXT_SERVER;
  readonly OPTIONS_CONTEXT_DISCOVERY = OPTIONS_CONTEXT_DISCOVERY;
  readonly OPTIONS_CONTEXT_CONNECTIONS = OPTIONS_CONTEXT_CONNECTIONS;
  readonly OPTIONS_CONTEXT_OTHER = OPTIONS_CONTEXT_OTHER;
  readonly OPTIONS_CONTEXT_AUTOQUEUE = OPTIONS_CONTEXT_AUTOQUEUE;
  readonly OPTIONS_CONTEXT_EXTRACT = OPTIONS_CONTEXT_EXTRACT;

  private readonly logger = inject(LoggerService);
  private readonly configService = inject(ConfigService);
  private readonly notifService = inject(NotificationService);
  private readonly commandService = inject(ServerCommandService);
  private readonly connectedService = inject(ConnectedService);

  readonly config$ = this.configService.config$;

  commandsEnabled = false;

  private configRestartNotif: Notification = createNotification(
    NotificationLevel.INFO,
    Localization.Notification.CONFIG_RESTART,
  );
  private badValueNotifs = new Map<string, Notification>();

  ngOnInit(): void {
    this.connectedService.connected$.subscribe({
      next: (connected: boolean) => {
        if (!connected) {
          this.notifService.hide(this.configRestartNotif);
        }
        this.commandsEnabled = connected;
      },
    });
  }

  getOptionValue(config: Config | null, valuePath: [string, string]): any {
    if (!config) return null;
    const section = (config as any)[valuePath[0]];
    if (!section) return null;
    return section[valuePath[1]] ?? null;
  }

  onSetConfig(section: string, option: string, value: any): void {
    this.configService.set(section, option, value).subscribe({
      next: (reaction) => {
        const notifKey = section + '.' + option;
        if (reaction.success) {
          this.logger.info(reaction.data);

          if (this.badValueNotifs.has(notifKey)) {
            this.notifService.hide(this.badValueNotifs.get(notifKey)!);
            this.badValueNotifs.delete(notifKey);
          }

          this.notifService.show(this.configRestartNotif);
        } else {
          const notif = createNotification(
            NotificationLevel.DANGER,
            reaction.errorMessage!,
            true,
          );
          if (this.badValueNotifs.has(notifKey)) {
            this.notifService.hide(this.badValueNotifs.get(notifKey)!);
          }
          this.notifService.show(notif);
          this.badValueNotifs.set(notifKey, notif);

          this.logger.error(reaction.errorMessage);
        }
      },
    });
  }

  onCommandRestart(): void {
    this.notifService.hide(this.configRestartNotif);

    this.commandService.restart().subscribe({
      next: (reaction) => {
        if (reaction.success) {
          this.logger.info(reaction.data);
        } else {
          this.logger.error(reaction.errorMessage);
        }
      },
    });
  }
}
