import { describe, expect, it } from "vitest";

import { formatDistance, phoneHref, safeExternalUrl } from "./agri-services";

describe("formatDistance", () => {
  it("shows metres below 1 km and kilometres above", () => {
    expect(formatDistance(0.5)).toBe("500 m");
    expect(formatDistance(0.24)).toBe("200 m");
    expect(formatDistance(1.24)).toBe("1.2 km");
    expect(formatDistance(8.44)).toBe("8.4 km");
  });

  it("handles zero and missing values", () => {
    expect(formatDistance(0)).toBe("0 m");
    expect(formatDistance(null)).toBe("");
    expect(formatDistance(undefined)).toBe("");
    expect(formatDistance(Number.NaN)).toBe("");
  });
});

describe("safeExternalUrl", () => {
  it("accepts http(s) URLs", () => {
    expect(safeExternalUrl("https://agriservices.example.com")).toBe("https://agriservices.example.com/");
    expect(safeExternalUrl("http://shop.example.in/contact")).toBe("http://shop.example.in/contact");
  });

  it("upgrades a bare domain to https", () => {
    expect(safeExternalUrl("shop.example.com")).toBe("https://shop.example.com/");
  });

  it("rejects injection schemes", () => {
    // Crowd-sourced OSM data could carry a hostile website tag.
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("data:text/html,<script>alert(1)</script>")).toBeNull();
    expect(safeExternalUrl("vbscript:msgbox(1)")).toBeNull();
    expect(safeExternalUrl("file:///etc/passwd")).toBeNull();
  });

  it("returns null for empty input", () => {
    expect(safeExternalUrl("")).toBeNull();
    expect(safeExternalUrl("   ")).toBeNull();
    expect(safeExternalUrl(null)).toBeNull();
    expect(safeExternalUrl(undefined)).toBeNull();
  });
});

describe("phoneHref", () => {
  it("builds a tel: link from a real number", () => {
    expect(phoneHref("+91 98220 11223")).toBe("tel:+919822011223");
    expect(phoneHref("(98480) 22110")).toBe("tel:9848022110");
  });

  it("refuses values that are not phone numbers", () => {
    expect(phoneHref("call the shop")).toBeNull();
    expect(phoneHref("")).toBeNull();
    expect(phoneHref(null)).toBeNull();
  });
});
