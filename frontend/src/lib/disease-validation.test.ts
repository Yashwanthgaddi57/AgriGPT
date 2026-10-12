import { describe, expect, it } from "vitest";

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic"];

function validateDiseaseImage(file: { size: number; type: string } | null): { valid: boolean; error?: string } {
  if (!file) {
    return { valid: false, error: "Please select an image file." };
  }
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    return { valid: false, error: "Unsupported image type. Use JPG, PNG, or WebP." };
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return { valid: false, error: "Image size exceeds 10MB limit." };
  }
  return { valid: true };
}

describe("Disease Scan Image Validation", () => {
  it("rejects null or unselected files", () => {
    expect(validateDiseaseImage(null).valid).toBe(false);
    expect(validateDiseaseImage(null).error).toBe("Please select an image file.");
  });

  it("accepts valid JPEG, PNG, and WebP files under 10MB", () => {
    expect(validateDiseaseImage({ size: 2 * 1024 * 1024, type: "image/jpeg" }).valid).toBe(true);
    expect(validateDiseaseImage({ size: 1024 * 1024, type: "image/png" }).valid).toBe(true);
    expect(validateDiseaseImage({ size: 500 * 1024, type: "image/webp" }).valid).toBe(true);
  });

  it("rejects unsupported MIME types like GIF or PDF", () => {
    const res = validateDiseaseImage({ size: 1024 * 1024, type: "image/gif" });
    expect(res.valid).toBe(false);
    expect(res.error).toContain("Unsupported image type");
  });

  it("rejects files exceeding 10MB limit", () => {
    const res = validateDiseaseImage({ size: 11 * 1024 * 1024, type: "image/jpeg" });
    expect(res.valid).toBe(false);
    expect(res.error).toContain("exceeds 10MB limit");
  });
});
