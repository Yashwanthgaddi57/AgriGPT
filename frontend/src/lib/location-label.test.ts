import { describe, expect, it } from "vitest";

import { formatLocationLabel } from "./location-label";

describe("formatLocationLabel", () => {
  it("uses the resolved label for a saved GPS fix", () => {
    expect(
      formatLocationLabel(
        { precision: "gps", label: "Ozar, Nashik, Maharashtra", village: "Ozar", district: "Nashik", state: "Maharashtra" },
        null,
        null
      )
    ).toBe("Ozar, Nashik, Maharashtra");
  });

  it("shows the state when the reverse geocode returned an empty district (the blank card bug)", () => {
    // This is the exact shape the API returns for a GPS user whose district is "".
    expect(
      formatLocationLabel(
        { precision: "gps", label: "Telangana", village: "", district: "", state: "Telangana" },
        { village: "", district: "", state: "Telangana" },
        { village: "", district: "", state: "Telangana" }
      )
    ).toBe("Telangana");
  });

  it("ignores empty and whitespace-only parts", () => {
    expect(
      formatLocationLabel({ precision: "map_pin", label: "  ", village: " ", district: "Pune", state: "" }, null, null)
    ).toBe("Pune");
  });

  it("falls back to the profile when there is no coordinate fix", () => {
    expect(
      formatLocationLabel(
        { precision: "district", label: "Nashik, Maharashtra", village: null, district: null, state: null },
        { village: null, district: "Nashik", state: "Maharashtra" },
        null
      )
    ).toBe("Nashik, Maharashtra");
  });

  it("falls back to the farm record last", () => {
    expect(formatLocationLabel(null, null, { district: "Guntur", state: "Andhra Pradesh" })).toBe(
      "Guntur, Andhra Pradesh"
    );
  });

  it("returns an empty string when nothing is known", () => {
    expect(formatLocationLabel({ precision: "district", label: "Nashik, Maharashtra" }, null, null)).toBe("");
    expect(formatLocationLabel(null, null, null)).toBe("");
  });
});
