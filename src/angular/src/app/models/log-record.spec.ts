import { describe, it, expect } from 'vitest';
import { logRecordFromJson, LogLevel, LogRecordJson } from './log-record';

describe('logRecordFromJson', () => {
  function makeJson(overrides: Partial<LogRecordJson> = {}): LogRecordJson {
    return {
      time: 1700000000,
      level_name: 'INFO',
      logger_name: 'seedsync.controller',
      message: 'Test message',
      exc_tb: '',
      ...overrides,
    };
  }

  it('should map level_name to LogLevel enum', () => {
    const levels: Array<[string, LogLevel]> = [
      ['DEBUG', LogLevel.DEBUG],
      ['INFO', LogLevel.INFO],
      ['WARNING', LogLevel.WARNING],
      ['ERROR', LogLevel.ERROR],
      ['CRITICAL', LogLevel.CRITICAL],
    ];

    for (const [input, expected] of levels) {
      const result = logRecordFromJson(makeJson({ level_name: input }));
      expect(result.level).toBe(expected);
    }
  });

  it('should fall back to INFO for unknown level', () => {
    const result = logRecordFromJson(makeJson({ level_name: 'TRACE' }));
    expect(result.level).toBe(LogLevel.INFO);
  });

  it('should convert timestamp from seconds to milliseconds', () => {
    const result = logRecordFromJson(makeJson({ time: 1700000000 }));
    expect(result.time).toEqual(new Date(1700000000 * 1000));
  });

  it('should map all snake_case fields to camelCase', () => {
    const json = makeJson({
      level_name: 'ERROR',
      logger_name: 'seedsync.lftp',
      message: 'Something failed',
      exc_tb: 'Traceback (most recent call last):\n  File ...',
    });

    const result = logRecordFromJson(json);

    expect(result.loggerName).toBe('seedsync.lftp');
    expect(result.message).toBe('Something failed');
    expect(result.exceptionTraceback).toBe('Traceback (most recent call last):\n  File ...');
  });
});
