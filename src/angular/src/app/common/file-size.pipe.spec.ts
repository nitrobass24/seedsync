import { describe, it, expect } from "vitest";
import { FileSizePipe } from "./file-size.pipe";

describe("FileSizePipe", () => {
  const pipe = new FileSizePipe();

  it("should return '0 B' for 0 bytes", () => {
    expect(pipe.transform(0)).toBe("0 B");
  });

  it("should return '1 KB' for 1024 bytes", () => {
    expect(pipe.transform(1024)).toBe("1 KB");
  });

  it("should return '1 MB' for 1048576 bytes", () => {
    expect(pipe.transform(1048576)).toBe("1 MB");
  });

  it("should return '1 GB' for 1073741824 bytes", () => {
    expect(pipe.transform(1073741824)).toBe("1 GB");
  });

  it("should return '1 TB' for 1099511627776 bytes", () => {
    expect(pipe.transform(1099511627776)).toBe("1 TB");
  });

  it("should return '1 PB' for 1125899906842624 bytes", () => {
    expect(pipe.transform(1125899906842624)).toBe("1 PB");
  });

  it("should return '?' for NaN", () => {
    expect(pipe.transform(NaN)).toBe("?");
  });

  it("should return '?' for Infinity", () => {
    expect(pipe.transform(Infinity)).toBe("?");
  });

  it("should respect custom precision", () => {
    expect(pipe.transform(1536, 3)).toBe("1.5 KB");
  });

  it("should return '0 B' when called with no arguments", () => {
    expect(pipe.transform()).toBe("0 B");
  });
});
