import { describe, it, expect } from "vitest";
import { EtaPipe } from "./eta.pipe";

describe("EtaPipe", () => {
  const pipe = new EtaPipe();

  it("should return '0s' for 0 seconds", () => {
    expect(pipe.transform(0)).toBe("0s");
  });

  it("should return '30s' for 30 seconds", () => {
    expect(pipe.transform(30)).toBe("30s");
  });

  it("should return '1m' for 60 seconds", () => {
    expect(pipe.transform(60)).toBe("1m");
  });

  it("should return '1m30s' for 90 seconds", () => {
    expect(pipe.transform(90)).toBe("1m30s");
  });

  it("should return '1h' for 3600 seconds", () => {
    expect(pipe.transform(3600)).toBe("1h");
  });

  it("should return '1h1m1s' for 3661 seconds", () => {
    expect(pipe.transform(3661)).toBe("1h1m1s");
  });

  it("should return '?' for NaN", () => {
    expect(pipe.transform(NaN)).toBe("?");
  });

  it("should return '?' for Infinity", () => {
    expect(pipe.transform(Infinity)).toBe("?");
  });

  it("should return '0s' when called with no arguments", () => {
    expect(pipe.transform()).toBe("0s");
  });
});
