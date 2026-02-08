import { Injectable } from '@angular/core';

export enum LogLevel {
  ERROR,
  WARN,
  INFO,
  DEBUG,
}

@Injectable({ providedIn: 'root' })
export class LoggerService {
  level = LogLevel.DEBUG;

  get debug() {
    return this.level >= LogLevel.DEBUG
      ? console.debug.bind(console)
      : () => {};
  }

  get info() {
    return this.level >= LogLevel.INFO
      ? console.log.bind(console)
      : () => {};
  }

  get warn() {
    return this.level >= LogLevel.WARN
      ? console.warn.bind(console)
      : () => {};
  }

  get error() {
    return this.level >= LogLevel.ERROR
      ? console.error.bind(console)
      : () => {};
  }
}
