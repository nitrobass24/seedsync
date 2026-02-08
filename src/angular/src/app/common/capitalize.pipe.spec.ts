import { describe, it, expect } from "vitest";
import { CapitalizePipe } from "./capitalize.pipe";

describe("CapitalizePipe", () => {
  const pipe = new CapitalizePipe();

  it("should capitalize the first letter of a lowercase string", () => {
    expect(pipe.transform("hello")).toBe("Hello");
  });

  it("should leave an already capitalized string unchanged", () => {
    expect(pipe.transform("HELLO")).toBe("HELLO");
  });

  it("should capitalize a single character", () => {
    expect(pipe.transform("a")).toBe("A");
  });

  it("should return empty string for empty string", () => {
    expect(pipe.transform("")).toBe("");
  });

  it("should return null for null", () => {
    expect(pipe.transform(null)).toBeNull();
  });

  it("should return undefined for undefined", () => {
    expect(pipe.transform(undefined)).toBeUndefined();
  });
});
