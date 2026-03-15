import { asHttpsUrl, parseLineList } from "~/lib/design-publish/form-utils";

export const renderPreviewImages = (
  previewValue: string,
  previewRenderList: HTMLElement | null,
  previousSignature: string,
): string => {
  if (!previewRenderList) return previousSignature;

  const previewValues = parseLineList(previewValue);
  const signature = previewValues.join("\n");
  if (signature === previousSignature) return previousSignature;

  previewRenderList.replaceChildren();
  if (previewValues.length === 0) {
    const empty = document.createElement("p");
    empty.className =
      "col-span-full rounded-md border border-dashed border-default/40 bg-default/[0.02] px-3 py-2 text-[11px] text-offset/75";
    empty.textContent = "No preview images yet.";
    previewRenderList.append(empty);
    return signature;
  }

  previewValues.forEach((rawUrl, index) => {
    const normalizedUrl = asHttpsUrl(rawUrl);
    const card = document.createElement("article");
    card.className = "space-y-1 rounded-md border border-default/40 bg-default/[0.02] p-1.5";

    const heading = document.createElement("div");
    heading.className = "flex items-center justify-between gap-2";

    const label = document.createElement("p");
    label.className = "truncate text-[11px] font-medium text-default/90";
    label.textContent = `Image ${index + 1}`;
    heading.append(label);

    const status = document.createElement("span");
    status.className = "shrink-0 text-[10px] text-offset/75";
    heading.append(status);

    const urlText = document.createElement("p");
    urlText.className = "truncate text-[11px] text-offset/80";
    urlText.textContent = rawUrl;

    card.append(heading, urlText);

    if (!normalizedUrl) {
      status.textContent = "Invalid URL";
      const invalidHint = document.createElement("p");
      invalidHint.className = "text-[11px] text-red-300/90";
      invalidHint.textContent = "Use a valid HTTPS URL to preview this image.";
      card.append(invalidHint);
      previewRenderList.append(card);
      return;
    }

    status.textContent = "Loading...";

    const imageWrap = document.createElement("div");
    imageWrap.className = "aspect-[3/4] overflow-hidden rounded border border-default/30 bg-default/5";

    const image = document.createElement("img");
    image.className = "h-full w-full object-cover";
    image.alt = `Preview image ${index + 1}`;
    image.loading = "lazy";
    image.decoding = "async";
    image.src = normalizedUrl;

    image.addEventListener("load", () => {
      status.textContent = "Loaded";
    });
    image.addEventListener("error", () => {
      status.textContent = "Failed to load";
      imageWrap.classList.add("border-red-400/40");
    });

    imageWrap.append(image);
    card.append(imageWrap);
    previewRenderList.append(card);
  });

  return signature;
};
