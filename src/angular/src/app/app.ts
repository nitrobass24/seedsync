import { AfterViewInit, Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';

import { ROUTE_INFOS, RouteInfo } from './routes';
import { DomService } from './services/utils/dom.service';
import { HeaderComponent } from './pages/main/header.component';
import { SidebarComponent } from './pages/main/sidebar.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, HeaderComponent, SidebarComponent],
  templateUrl: './app.html',
  styleUrls: ['./app.scss']
})
export class App implements OnInit, AfterViewInit {
  @ViewChild('topHeader') topHeader!: ElementRef;

  showSidebar = false;
  activeRoute: RouteInfo | undefined;

  private _resizeObserver: ResizeObserver | null = null;

  constructor(
    private router: Router,
    private _domService: DomService
  ) {
    router.events.subscribe(() => {
      this.showSidebar = false;
      this.activeRoute = ROUTE_INFOS.find(value => '/' + value.path === router.url);
    });
  }

  ngOnInit() {
    this.router.events.subscribe((evt) => {
      if (!(evt instanceof NavigationEnd)) {
        return;
      }
      window.scrollTo(0, 0);
    });
  }

  ngAfterViewInit() {
    this._resizeObserver = new ResizeObserver(() => {
      this._domService.setHeaderHeight(this.topHeader.nativeElement.clientHeight);
    });
    this._resizeObserver.observe(this.topHeader.nativeElement);
  }
}
