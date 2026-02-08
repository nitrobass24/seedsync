import { describe, it, expect } from 'vitest';
import { CachedReuseStrategy } from './cached-reuse-strategy';

describe('CachedReuseStrategy', () => {
  let strategy: CachedReuseStrategy;

  function makeRoute(path: string) {
    return { routeConfig: { path } } as any;
  }

  beforeEach(() => {
    strategy = new CachedReuseStrategy();
  });

  it('shouldDetach should always return true', () => {
    expect(strategy.shouldDetach(makeRoute('files'))).toBe(true);
    expect(strategy.shouldDetach(makeRoute('logs'))).toBe(true);
    expect(strategy.shouldDetach({ routeConfig: null } as any)).toBe(true);
  });

  it('store and retrieve should round-trip a handle', () => {
    const route = makeRoute('files');
    const handle = { component: 'fake' } as any;

    strategy.store(route, handle);
    const retrieved = strategy.retrieve(route);

    expect(retrieved).toBe(handle);
  });

  it('shouldAttach should return true only if previously stored', () => {
    const route = makeRoute('files');
    const otherRoute = makeRoute('logs');
    const handle = { component: 'fake' } as any;

    expect(strategy.shouldAttach(route)).toBe(false);

    strategy.store(route, handle);

    expect(strategy.shouldAttach(route)).toBe(true);
    expect(strategy.shouldAttach(otherRoute)).toBe(false);
  });

  it('shouldAttach should return false when routeConfig is null or undefined', () => {
    expect(strategy.shouldAttach({ routeConfig: null } as any)).toBe(false);
    expect(strategy.shouldAttach({ routeConfig: undefined } as any)).toBe(false);
    expect(strategy.shouldAttach({} as any)).toBe(false);
  });

  it('retrieve should return null when routeConfig is null', () => {
    expect(strategy.retrieve({ routeConfig: null } as any)).toBeNull();
    expect(strategy.retrieve({ routeConfig: undefined } as any)).toBeNull();
  });

  it('shouldReuseRoute should return true when same config, false when different', () => {
    const config = { path: 'files' };
    const route1 = { routeConfig: config } as any;
    const route2 = { routeConfig: config } as any;
    const route3 = { routeConfig: { path: 'files' } } as any;

    expect(strategy.shouldReuseRoute(route1, route2)).toBe(true);
    expect(strategy.shouldReuseRoute(route1, route3)).toBe(false);
  });
});
