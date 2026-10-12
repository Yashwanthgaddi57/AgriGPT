import { describe, expect, it } from "vitest";
import {
  cn,
  formatCompactINR,
  formatDate,
  formatINR,
  formatPercent,
  riskLabel,
} from "./utils";

describe("formatINR", () => {
  it("formats standard INR amounts with symbol", () => {
    const formatted = formatINR(50000);
    // Currency formatting might vary slightly across Node/OS locale spaces (NBSP vs regular space)
    expect(formatted.replace(/\s+/g, " ")).toMatch(/₹\s*50,000/);
  });

  it("handles null or NaN safely by returning ₹0", () => {
    expect(formatINR(null).replace(/\s+/g, " ")).toMatch(/₹\s*0/);
    expect(formatINR("not a number").replace(/\s+/g, " ")).toMatch(/₹\s*0/);
  });
});

describe("formatCompactINR", () => {
  it("compacts crores (1e7)", () => {
    expect(formatCompactINR(15000000)).toBe("₹1.50 Cr");
  });

  it("compacts lakhs (1e5)", () => {
    expect(formatCompactINR(250000)).toBe("₹2.50 L");
  });

  it("compacts thousands (1e3)", () => {
    expect(formatCompactINR(4500)).toBe("₹4.5K");
  });

  it("handles numbers under 1000", () => {
    expect(formatCompactINR(850)).toBe("₹850");
  });

  it("handles null or undefined safely", () => {
    expect(formatCompactINR(null)).toBe("₹0");
    expect(formatCompactINR(undefined)).toBe("₹0");
  });
});

describe("formatPercent", () => {
  it("adds plus sign for positive percentages", () => {
    expect(formatPercent(12.5)).toBe("+12.5%");
  });

  it("formats zero percentage with plus sign", () => {
    expect(formatPercent(0)).toBe("+0.0%");
  });

  it("formats negative percentage without extra sign", () => {
    expect(formatPercent(-8.3)).toBe("-8.3%");
  });
});

describe("formatDate", () => {
  it("returns dash for empty dates", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("")).toBe("—");
  });

  it("formats valid date string", () => {
    const formatted = formatDate("2026-03-15T00:00:00Z");
    expect(formatted).toContain("2026");
    expect(formatted).toContain("Mar");
  });
});

describe("riskLabel", () => {
  it("returns High for score >= 70", () => {
    const res = riskLabel(75);
    expect(res.label).toBe("High");
    expect(res.color).toContain("red");
  });

  it("returns Medium for score between 40 and 69", () => {
    const res = riskLabel(55);
    expect(res.label).toBe("Medium");
    expect(res.color).toContain("amber");
  });

  it("returns Low for score < 40", () => {
    const res = riskLabel(25);
    expect(res.label).toBe("Low");
    expect(res.color).toContain("leaf");
  });
});

describe("cn utility", () => {
  it("merges classes cleanly removing duplicate tailwind classes", () => {
    expect(cn("px-2 py-1", "px-4")).toBe("py-1 px-4");
  });
});
