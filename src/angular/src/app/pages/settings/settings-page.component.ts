import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AsyncPipe, NgTemplateOutlet, TitleCasePipe } from '@angular/common';
import { distinctUntilChanged, map } from 'rxjs';

import { LoggerService } from '../../services/utils/logger.service';
import { ConfigService } from '../../services/settings/config.service';
import { NotificationService } from '../../services/utils/notification.service';
import { NotificationChannel, NotificationsService, NOTIFICATION_CHANNELS } from '../../services/settings/notifications.service';
import { TestResult } from '../../services/utils/test-result';
import { ServerCommandService } from '../../services/server/server-command.service';
import { ConnectedService } from '../../services/utils/connected.service';
import { PathPairsService } from '../../services/settings/path-pairs.service';
import { Notification, NotificationLevel, createNotification } from '../../models/notification';
import { Localization } from '../../models/localization';
import { Config } from '../../models/config';
import { ClickStopPropagationDirective } from '../../common/click-stop-propagation.directive';
import { OptionComponent, OptionValue } from './option.component';
import { PathPairsComponent } from './path-pairs.component';
import { IntegrationsComponent } from './integrations.component';
import {
  ActiveDisableFlags,
  ConfigValuePath,
  IOptionsContext,
  applyDisableRules,
  getConfigValue,
  OPTIONS_CONTEXT_SERVER,
  OPTIONS_CONTEXT_FTPS,
  OPTIONS_CONTEXT_DISCOVERY,
  OPTIONS_CONTEXT_CONNECTIONS,
  OPTIONS_CONTEXT_OTHER,
  OPTIONS_CONTEXT_AUTOQUEUE,
  OPTIONS_CONTEXT_STAGING,
  OPTIONS_CONTEXT_EXTRACT,
  OPTIONS_CONTEXT_VALIDATE,
  OPTIONS_CONTEXT_ADVANCED_LFTP,
  OPTIONS_CONTEXT_LOGGING,
  OPTIONS_CONTEXT_NOTIFICATIONS,
} from './options-list';

@Component({
  selector: 'app-settings-page',
  standalone: true,
  imports: [
    AsyncPipe,
    NgTemplateOutlet,
    TitleCasePipe,
    OptionComponent,
    PathPairsComponent,
    IntegrationsComponent,
    ClickStopPropagationDirective,
  ],
  templateUrl: './settings-page.component.html',
  styleUrls: ['./settings-page.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsPageComponent implements OnInit {
  serverContext: IOptionsContext = OPTIONS_CONTEXT_SERVER;
  ftpsContext: IOptionsContext = OPTIONS_CONTEXT_FTPS;
  autoqueueContext: IOptionsContext = OPTIONS_CONTEXT_AUTOQUEUE;
  validateContext: IOptionsContext = OPTIONS_CONTEXT_VALIDATE;
  readonly OPTIONS = {
    discovery: OPTIONS_CONTEXT_DISCOVERY,
    connections: OPTIONS_CONTEXT_CONNECTIONS,
    other: OPTIONS_CONTEXT_OTHER,
    staging: OPTIONS_CONTEXT_STAGING,
    extract: OPTIONS_CONTEXT_EXTRACT,
    advancedLftp: OPTIONS_CONTEXT_ADVANCED_LFTP,
    logging: OPTIONS_CONTEXT_LOGGING,
    notifications: OPTIONS_CONTEXT_NOTIFICATIONS,
  };
  readonly CHANNELS = NOTIFICATION_CHANNELS;

  advancedLftpCollapsed = true;

  private readonly logger = inject(LoggerService);
  private readonly configService = inject(ConfigService);
  private readonly notifService = inject(NotificationService);
  private readonly notificationsService = inject(NotificationsService);
  private readonly commandService = inject(ServerCommandService);
  private readonly connectedService = inject(ConnectedService);
  private readonly pathPairsService = inject(PathPairsService);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly destroyRef = inject(DestroyRef);

  readonly config$ = this.configService.config$;

  commandsEnabled = false;
  testing: Record<NotificationChannel, boolean> = { discord: false, telegram: false };
  results: Record<NotificationChannel, TestResult | null> = { discord: null, telegram: null };

  private readonly active: ActiveDisableFlags = { pairsEnabled: false, validateDisabled: false, protocolSftp: false };

  private configRestartNotif: Notification = createNotification(
    NotificationLevel.INFO,
    Localization.Notification.CONFIG_RESTART,
  );
  private badValueNotifs = new Map<string, Notification>();

  ngOnInit(): void {
    this.connectedService.connected$.pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: (connected: boolean) => {
        if (!connected) {
          this.notifService.hide(this.configRestartNotif);
        }
        this.commandsEnabled = connected;
        this.cdr.markForCheck();
      },
    });

    this.pathPairsService.pairs$.pipe(
      map((pairs) => pairs.some((p) => p.enabled)),
      distinctUntilChanged(),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((hasEnabledPairs) => {
      this.active.pairsEnabled = hasEnabledPairs;
      this.rebuildContexts();
    });

    this.configService.config$.pipe(
      map((config) => ({
        validateEnabled: config?.validate?.enabled ?? false,
        protocolIsSftp: (config?.lftp?.protocol ?? 'sftp') !== 'ftps',
      })),
      distinctUntilChanged(
        (a, b) => a.validateEnabled === b.validateEnabled && a.protocolIsSftp === b.protocolIsSftp,
      ),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(({ validateEnabled, protocolIsSftp }) => {
      this.active.validateDisabled = !validateEnabled;
      this.active.protocolSftp = protocolIsSftp;
      this.rebuildContexts();
    });
  }

  private rebuildContexts(): void {
    this.serverContext = applyDisableRules(OPTIONS_CONTEXT_SERVER, this.active);
    this.ftpsContext = applyDisableRules(OPTIONS_CONTEXT_FTPS, this.active);
    this.autoqueueContext = applyDisableRules(OPTIONS_CONTEXT_AUTOQUEUE, this.active);
    this.validateContext = applyDisableRules(OPTIONS_CONTEXT_VALIDATE, this.active);
    this.cdr.markForCheck();
  }

  getOptionValue(config: Config | null, valuePath: ConfigValuePath): OptionValue {
    if (!config) return null;
    return getConfigValue(config, valuePath);
  }

  onSetConfig(section: string, option: string, value: OptionValue, requiresRestart?: boolean): void {
    this.configService.set(section, option, value).subscribe({
      next: (reaction) => {
        const notifKey = section + '.' + option;
        if (reaction.success) {
          this.logger.info(reaction.data);

          if (this.badValueNotifs.has(notifKey)) {
            this.notifService.hide(this.badValueNotifs.get(notifKey)!);
            this.badValueNotifs.delete(notifKey);
          }

          if (requiresRestart) {
            this.notifService.show(this.configRestartNotif);
          }
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

  toggleAdvancedLftp(): void {
    this.advancedLftpCollapsed = !this.advancedLftpCollapsed;
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

  onTest(channel: NotificationChannel): void {
    this.testing[channel] = true;
    this.results[channel] = null;
    this.notificationsService.test(channel).pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((result) => {
      this.testing[channel] = false;
      this.results[channel] = result;
      this.cdr.markForCheck();
    });
  }
}
