import { Injectable } from '@angular/core';

/** Thin console facade so specs can stub logging via DI. */
@Injectable({ providedIn: 'root' })
export class LoggerService {
  get debug() { return console.debug.bind(console); }
  get info() { return console.log.bind(console); }
  get warn() { return console.warn.bind(console); }
  get error() { return console.error.bind(console); }
}
