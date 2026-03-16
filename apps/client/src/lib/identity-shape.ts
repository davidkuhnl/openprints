const EMOJI_RE = /\p{Extended_Pictographic}/u;

const splitGraphemes = (value: string): string[] => {
  if (
    typeof Intl !== "undefined" &&
    "Segmenter" in Intl &&
    typeof Intl.Segmenter === "function"
  ) {
    const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });
    return Array.from(segmenter.segment(value), (part) => part.segment);
  }
  return Array.from(value);
};

export const normalizeIdentityShape = (value: string | null | undefined): string | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;

  const graphemes = splitGraphemes(trimmed);
  if (graphemes.length !== 1) return null;
  if (!EMOJI_RE.test(graphemes[0])) return null;
  return graphemes[0];
};

export const buildIdentityShapeMaskDataUri = (emoji: string): string => {
  if (typeof document === "undefined") {
    return "";
  }

  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";

  ctx.clearRect(0, 0, 128, 128);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font =
    '108px "Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif';
  ctx.fillStyle = "#ffffff";
  ctx.fillText(emoji, 64, 68);

  const image = ctx.getImageData(0, 0, 128, 128).data;
  let alphaPixels = 0;
  let minX = 127;
  let minY = 127;
  let maxX = 0;
  let maxY = 0;
  for (let y = 0; y < 128; y += 1) {
    for (let x = 0; x < 128; x += 1) {
      const alpha = image[(y * 128 + x) * 4 + 3];
      if (alpha > 8) {
        alphaPixels += 1;
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
      }
    }
  }

  if (alphaPixels < 100) return "";
  const bboxArea = (maxX - minX + 1) * (maxY - minY + 1);
  if (bboxArea <= 0) return "";
  const fillRatio = alphaPixels / bboxArea;
  // Likely unsupported emoji/tofu box: avoid square fallback and use circle.
  if (fillRatio > 0.92) return "";

  return canvas.toDataURL("image/png");
};

