import { Component, OnInit, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { ROUTE_INFOS } from '../../routes';
import { ServerCommandService } from '../../services/server/server-command.service';
import { LoggerService } from '../../services/utils/logger.service';
import { ConnectedService } from '../../services/utils/connected.service';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './sidebar.component.html',
  styleUrls: ['./sidebar.component.scss']
})
export class SidebarComponent implements OnInit {
  routeInfos = ROUTE_INFOS;

  public commandsEnabled = false;

  private readonly _logger = inject(LoggerService);
  private readonly _connectedService = inject(ConnectedService);
  private readonly _commandService = inject(ServerCommandService);

  ngOnInit() {
    this._connectedService.connected$.subscribe({
      next: (connected: boolean) => {
        this.commandsEnabled = connected;
      }
    });
  }

  onCommandRestart() {
    this._commandService.restart().subscribe({
      next: reaction => {
        if (reaction.success) {
          this._logger.info(reaction.data);
        } else {
          this._logger.error(reaction.errorMessage);
        }
      }
    });
  }
}
