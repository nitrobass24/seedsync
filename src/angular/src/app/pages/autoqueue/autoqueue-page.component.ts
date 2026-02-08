import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AsyncPipe } from '@angular/common';

import { AutoQueueService } from '../../services/autoqueue/autoqueue.service';
import { AutoQueuePattern } from '../../models/autoqueue-pattern';
import { NotificationService } from '../../services/utils/notification.service';
import { ConnectedService } from '../../services/utils/connected.service';
import { ConfigService } from '../../services/settings/config.service';
import { createNotification, NotificationLevel } from '../../models/notification';
import { ClickStopPropagationDirective } from '../../common/click-stop-propagation.directive';

@Component({
  selector: 'app-autoqueue-page',
  standalone: true,
  imports: [FormsModule, AsyncPipe, ClickStopPropagationDirective],
  templateUrl: './autoqueue-page.component.html',
  styleUrls: ['./autoqueue-page.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AutoQueuePageComponent implements OnInit {
  private readonly changeDetector = inject(ChangeDetectorRef);
  private readonly autoqueueService = inject(AutoQueueService);
  private readonly notifService = inject(NotificationService);
  private readonly configService = inject(ConfigService);
  private readonly connectedService = inject(ConnectedService);

  readonly patterns$ = this.autoqueueService.patterns$;

  newPattern = '';
  connected = false;
  enabled = false;
  patternsOnly = false;

  ngOnInit(): void {
    this.connectedService.connected$.subscribe({
      next: (connected: boolean) => {
        this.connected = connected;
        if (!this.connected) {
          this.newPattern = '';
        }
      },
    });

    this.configService.config$.subscribe({
      next: (config) => {
        if (config != null) {
          this.enabled = !!config.autoqueue.enabled;
          this.patternsOnly = !!config.autoqueue.patterns_only;
        } else {
          this.enabled = false;
          this.patternsOnly = false;
        }
        this.changeDetector.detectChanges();
      },
    });
  }

  onAddPattern(): void {
    this.autoqueueService.add(this.newPattern).subscribe({
      next: (reaction) => {
        if (reaction.success) {
          this.newPattern = '';
        } else {
          const notif = createNotification(
            NotificationLevel.DANGER,
            reaction.errorMessage!,
            true,
          );
          this.notifService.show(notif);
        }
      },
    });
  }

  onRemovePattern(pattern: AutoQueuePattern): void {
    this.autoqueueService.remove(pattern.pattern).subscribe({
      next: (reaction) => {
        if (!reaction.success) {
          const notif = createNotification(
            NotificationLevel.DANGER,
            reaction.errorMessage!,
            true,
          );
          this.notifService.show(notif);
        }
      },
    });
  }
}
