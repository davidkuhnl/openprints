const EMOJI_RE = /\p{Extended_Pictographic}/u;

const WORK_SIZE = 128;
const OUTPUT_SIZE = 256;
const ALPHA_THRESHOLD = 8;
const MIN_ALPHA_PIXELS = 100;

const shapeMaskCache = new Map<string, string | null>();

let workCanvas: HTMLCanvasElement | null = null;
let workCtx: CanvasRenderingContext2D | null = null;

let outputCanvas: HTMLCanvasElement | null = null;
let outputCtx: CanvasRenderingContext2D | null = null;

const getCanvasContext = (
  kind: "work" | "output",
): { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D } | null => {
  if (typeof document === "undefined") return null;

  if (kind === "work") {
    if (!workCanvas) {
      workCanvas = document.createElement("canvas");
      workCanvas.width = WORK_SIZE;
      workCanvas.height = WORK_SIZE;
      workCtx = workCanvas.getContext("2d");
    }
    if (!workCanvas || !workCtx) return null;
    return { canvas: workCanvas, ctx: workCtx };
  }

  if (!outputCanvas) {
    outputCanvas = document.createElement("canvas");
    outputCanvas.width = OUTPUT_SIZE;
    outputCanvas.height = OUTPUT_SIZE;
    outputCtx = outputCanvas.getContext("2d");
  }
  if (!outputCanvas || !outputCtx) return null;
  return { canvas: outputCanvas, ctx: outputCtx };
};

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

export const normalizeIdentityShape = (
  value: string | null | undefined,
): string | null => {
  if (typeof value !== "string") return null;

  const trimmed = value.trim();
  if (!trimmed) return null;

  const graphemes = splitGraphemes(trimmed);
  if (graphemes.length !== 1) return null;
  if (!EMOJI_RE.test(graphemes[0])) return null;

  return graphemes[0];
};

const clearMaskStyles = (element?: HTMLElement | null): void => {
  if (!element) return;

  element.style.removeProperty("-webkit-mask-image");
  element.style.removeProperty("mask-image");
  element.style.removeProperty("-webkit-mask-size");
  element.style.removeProperty("mask-size");
  element.style.removeProperty("-webkit-mask-repeat");
  element.style.removeProperty("mask-repeat");
  element.style.removeProperty("-webkit-mask-position");
  element.style.removeProperty("mask-position");
  element.style.removeProperty("-webkit-mask-mode");
  element.style.removeProperty("mask-mode");
};

const clearMaskVariable = (element?: HTMLElement | null): void => {
  if (!element) return;
  element.style.removeProperty("--identity-avatar-mask");
};

const buildIdentityShapeMaskDataUriUncached = (emoji: string): string => {
  const work = getCanvasContext("work");
  const output = getCanvasContext("output");
  if (!work || !output) return "";

  const { canvas: srcCanvas, ctx: srcCtx } = work;
  const { canvas: dstCanvas, ctx: dstCtx } = output;

  srcCtx.clearRect(0, 0, WORK_SIZE, WORK_SIZE);
  srcCtx.textAlign = "center";
  srcCtx.textBaseline = "middle";
  srcCtx.font =
    '108px "Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif';
  srcCtx.fillStyle = "#ffffff";
  srcCtx.fillText(emoji, WORK_SIZE / 2, 68);

  const image = srcCtx.getImageData(0, 0, WORK_SIZE, WORK_SIZE).data;

  let alphaPixels = 0;
  let minX = WORK_SIZE - 1;
  let minY = WORK_SIZE - 1;
  let maxX = 0;
  let maxY = 0;

  for (let y = 0; y < WORK_SIZE; y += 1) {
    for (let x = 0; x < WORK_SIZE; x += 1) {
      const alpha = image[(y * WORK_SIZE + x) * 4 + 3];
      if (alpha > ALPHA_THRESHOLD) {
        alphaPixels += 1;
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
      }
    }
  }

  if (alphaPixels < MIN_ALPHA_PIXELS) return "";

  const bboxWidth = maxX - minX + 1;
  const bboxHeight = maxY - minY + 1;
  const bboxArea = bboxWidth * bboxHeight;
  if (bboxArea <= 0) return "";

  const fillRatio = alphaPixels / bboxArea;

  // Likely tofu / unsupported fallback glyph.
  if (fillRatio > 0.92) return "";

  // Crop to tight bounds, then place into a square output canvas so that
  // scaling is consistent across avatar sizes.
  const cropSize = Math.max(bboxWidth, bboxHeight);
  const cropX = minX - (cropSize - bboxWidth) / 2;
  const cropY = minY - (cropSize - bboxHeight) / 2;

  dstCtx.clearRect(0, 0, OUTPUT_SIZE, OUTPUT_SIZE);
  dstCtx.drawImage(
    srcCanvas,
    cropX,
    cropY,
    cropSize,
    cropSize,
    0,
    0,
    OUTPUT_SIZE,
    OUTPUT_SIZE,
  );

  return dstCanvas.toDataURL("image/png");
};

export const buildIdentityShapeMaskDataUri = (emoji: string): string => {
  if (typeof document === "undefined") return "";

  const cached = shapeMaskCache.get(emoji);
  if (cached !== undefined) return cached ?? "";

  const result = buildIdentityShapeMaskDataUriUncached(emoji);
  shapeMaskCache.set(emoji, result || null);
  return result;
};

export const applyIdentityShapeMaskToElements = (
  shapeRaw: string | null | undefined,
  root: HTMLElement | null,
  shellEl?: HTMLElement | null,
  clipEl?: HTMLElement | null,
): void => {
  if (!root) return;

  const normalized = normalizeIdentityShape(shapeRaw);

  const clearShapeMask = () => {
    root.setAttribute("data-shape-mode", "circle");
    root.removeAttribute("data-shape-emoji");
    clearMaskVariable(root);

    for (const element of [shellEl, clipEl]) {
      clearMaskStyles(element);
    }
  };

  if (!normalized) {
    clearShapeMask();
    return;
  }

  // Avoid doing DOM work again if already applied.
  if (
    root.getAttribute("data-shape-mode") === "emoji" &&
    root.getAttribute("data-shape-emoji") === normalized
  ) {
    return;
  }

  const maskSrc = buildIdentityShapeMaskDataUri(normalized);
  if (!maskSrc) {
    clearShapeMask();
    return;
  }

  const maskValue = `url("${maskSrc}")`;

  root.setAttribute("data-shape-mode", "emoji");
  root.setAttribute("data-shape-emoji", normalized);
  root.style.setProperty("--identity-avatar-mask", maskValue);

  for (const element of [shellEl, clipEl]) {
    clearMaskStyles(element);
  }
};
