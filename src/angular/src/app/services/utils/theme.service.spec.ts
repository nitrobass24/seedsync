import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { TestBed } from "@angular/core/testing";
import { ThemeService, Theme } from "./theme.service";
import { LoggerService } from "./logger.service";
import { StorageKeys } from "../../common/storage-keys";

describe("ThemeService", () => {
  let service: ThemeService;
  let store: Record<string, string> = {};
  let matchMediaResult = false;
  let originalMatchMedia: typeof window.matchMedia;

  beforeEach(() => {
    store = {};
    matchMediaResult = false;

    // Save and replace matchMedia (may not exist in happy-dom)
    originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn((query: string) => ({
      matches: matchMediaResult,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })) as unknown as typeof window.matchMedia;

    // Mock localStorage methods directly
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => store[key] ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key];
      }),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(),
    });

    // Reset the document attribute before each test
    document.documentElement.removeAttribute("data-bs-theme");
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function createService(): ThemeService {
    TestBed.configureTestingModule({
      providers: [
        ThemeService,
        {
          provide: LoggerService,
          useValue: {
            debug: vi.fn(),
            error: vi.fn(),
            info: vi.fn(),
            warn: vi.fn(),
          },
        },
      ],
    });
    return TestBed.inject(ThemeService);
  }

  function latestTheme(): Theme {
    let result: Theme | undefined;
    service.theme$.subscribe((t) => (result = t));
    return result!;
  }

  // --- Initialization ---

  it("should default to light when system prefers light", () => {
    matchMediaResult = false;
    service = createService();

    expect(latestTheme()).toBe("light");
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe(
      "light",
    );
  });

  it("should default to dark when system prefers dark", () => {
    matchMediaResult = true;
    service = createService();

    expect(latestTheme()).toBe("dark");
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe("dark");
  });

  it("should respect stored localStorage preference over system preference", () => {
    matchMediaResult = true; // system says dark
    store[StorageKeys.THEME] = "light"; // user chose light
    service = createService();

    expect(latestTheme()).toBe("light");
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe(
      "light",
    );
  });

  it("should respect stored dark preference from localStorage", () => {
    matchMediaResult = false; // system says light
    store[StorageKeys.THEME] = "dark"; // user chose dark
    service = createService();

    expect(latestTheme()).toBe("dark");
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe("dark");
  });

  // --- Toggle ---

  it("should toggle from light to dark and persist", () => {
    matchMediaResult = false;
    service = createService();

    service.toggle();

    expect(latestTheme()).toBe("dark");
    expect(store[StorageKeys.THEME]).toBe("dark");
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe("dark");
  });

  it("should toggle from dark to light and persist", () => {
    store[StorageKeys.THEME] = "dark";
    service = createService();

    service.toggle();

    expect(latestTheme()).toBe("light");
    expect(store[StorageKeys.THEME]).toBe("light");
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe(
      "light",
    );
  });

  it("should set data-bs-theme on document element", () => {
    service = createService();

    expect(document.documentElement.getAttribute("data-bs-theme")).toBe(
      "light",
    );

    service.toggle();
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe("dark");

    service.toggle();
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe(
      "light",
    );
  });
});
