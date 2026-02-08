/**
 * LogRecord model.
 */
export interface LogRecord {
  time: Date;
  level: LogLevel;
  loggerName: string;
  message: string;
  exceptionTraceback: string | null;
}

export enum LogLevel {
  DEBUG    = 'DEBUG',
  INFO     = 'INFO',
  WARNING  = 'WARNING',
  ERROR    = 'ERROR',
  CRITICAL = 'CRITICAL',
}

/**
 * LogRecord as serialized by the backend.
 * Note: naming convention matches that used in JSON.
 */
export interface LogRecordJson {
  time: number;
  level_name: string;
  logger_name: string;
  message: string;
  exc_tb: string;
}

const LEVEL_LOOKUP: Record<string, LogLevel> = {
  DEBUG:    LogLevel.DEBUG,
  INFO:     LogLevel.INFO,
  WARNING:  LogLevel.WARNING,
  ERROR:    LogLevel.ERROR,
  CRITICAL: LogLevel.CRITICAL,
};

export function logRecordFromJson(json: LogRecordJson): LogRecord {
  return {
    time: new Date(1000 * +json.time),
    level: LEVEL_LOOKUP[json.level_name] ?? LogLevel.INFO,
    loggerName: json.logger_name,
    message: json.message,
    exceptionTraceback: json.exc_tb,
  };
}
