import { Component } from '@angular/core';

import packageJson from '../../../../package.json';

@Component({
  selector: 'app-about-page',
  standalone: true,
  templateUrl: './about-page.component.html',
  styleUrls: ['./about-page.component.scss'],
})
export class AboutPageComponent {
  readonly version = packageJson.version;
}
