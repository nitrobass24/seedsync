import { ChangeDetectionStrategy, ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AsyncPipe, NgTemplateOutlet } from '@angular/common';
import { distinctUntilChanged, map } from 'rxjs';

import { LoggerService } from '../../services/utils/logger.service';
import { ConfigService } from '../../services/settings/config.service';
import { NotificationService } from '../../services/utils/notification.service';
import { NotificationsService, TestResult } from '../../services/settings/notifications.service';
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
  IOptionsContext,
  OPTIONS_CONTEXT_SERVER,
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
  autoqueueContext: IOptionsContext = OPTIONS_CONTEXT_AUTOQUEUE;
  validateContext: IOptionsContext = OPTIONS_CONTEXT_VALIDATE;
  readonly OPTIONS_CONTEXT_DISCOVERY = OPTIONS_CONTEXT_DISCOVERY;
  readonly OPTIONS_CONTEXT_CONNECTIONS = OPTIONS_CONTEXT_CONNECTIONS;
  readonly OPTIONS_CONTEXT_OTHER = OPTIONS_CONTEXT_OTHER;
  readonly OPTIONS_CONTEXT_STAGING = OPTIONS_CONTEXT_STAGING;
  readonly OPTIONS_CONTEXT_EXTRACT = OPTIONS_CONTEXT_EXTRACT;
  readonly OPTIONS_CONTEXT_ADVANCED_LFTP = OPTIONS_CONTEXT_ADVANCED_LFTP;
  readonly OPTIONS_CONTEXT_LOGGING = OPTIONS_CONTEXT_LOGGING;
  readonly OPTIONS_CONTEXT_NOTIFICATIONS = OPTIONS_CONTEXT_NOTIFICATIONS;

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
  testingDiscord = false;
  testingTelegram = false;
  discordResult: TestResult | null = null;
  telegramResult: TestResult | null = null;

  private configRestartNotif: Notification = createNotification(
    NotificationLevel.INFO,
    Localization.Notification.CONFIG_RESTART,
  );
  private badValueNotifs = new Map<string, Notification>();

  private static readonly OVERRIDE_NOTE = 'Overridden by Path Pairs when any pair is enabled';

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
      this.serverContext = SettingsPageComponent.buildServerContext(hasEnabledPairs);
      this.autoqueueContext = SettingsPageComponent.buildAutoqueueContext(hasEnabledPairs);
      this.cdr.markForCheck();
    });

    this.configService.config$.pipe(
      map((config) => config?.validate?.enabled ?? false),
      distinctUntilChanged(),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((validateEnabled) => {
      this.validateContext = SettingsPageComponent.buildValidateContext(validateEnabled);
      this.cdr.markForCheck();
    });
  }

  private static buildServerContext(hasEnabledPairs: boolean): IOptionsContext {
    return {
      ...OPTIONS_CONTEXT_SERVER,
      options: OPTIONS_CONTEXT_SERVER.options.map((option) => {
        if (hasEnabledPairs && (option.valuePath[1] === 'remote_path' || option.valuePath[1] === 'local_path')) {
          return { ...option, description: SettingsPageComponent.OVERRIDE_NOTE, disabled: true };
        }
        return option;
      }),
    };
  }

  private static buildAutoqueueContext(hasEnabledPairs: boolean): IOptionsContext {
    return {
      ...OPTIONS_CONTEXT_AUTOQUEUE,
      options: OPTIONS_CONTEXT_AUTOQUEUE.options.map((option) => {
        if (hasEnabledPairs && option.valuePath[1] === 'enabled') {
          return { ...option, description: SettingsPageComponent.OVERRIDE_NOTE, disabled: true };
        }
        return option;
      }),
    };
  }

  private static buildValidateContext(validateEnabled: boolean): IOptionsContext {
    return {
      ...OPTIONS_CONTEXT_VALIDATE,
      options: OPTIONS_CONTEXT_VALIDATE.options.map((option) => {
        if (!validateEnabled && (option.valuePath[1] === 'auto_validate' || option.valuePath[1] === 'algorithm')) {
          return { ...option, disabled: true };
        }
        return option;
      }),
    };
  }

  getOptionValue(config: Config | null, valuePath: [string, string]): OptionValue {
    if (!config) return null;
    const section = (config as unknown as Record<string, Record<string, OptionValue> | undefined>)[valuePath[0]];
    if (!section) return null;
    return section[valuePath[1]] ?? null;
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

  onTestDiscord(): void {
    this.testingDiscord = true;
    this.discordResult = null;
    this.notificationsService.testDiscord().pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((result) => {
      this.testingDiscord = false;
      this.discordResult = result;
      this.cdr.markForCheck();
    });
  }

  onTestTelegram(): void {
    this.testingTelegram = true;
    this.telegramResult = null;
    this.notificationsService.testTelegram().pipe(
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((result) => {
      this.testingTelegram = false;
      this.telegramResult = result;
      this.cdr.markForCheck();
    });
  }
}
