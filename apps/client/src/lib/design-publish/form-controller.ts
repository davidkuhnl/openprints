import {
  signWithCurrentSigner,
  startIdentityStore,
  subscribeToCurrentIdentity,
  type IdentitySnapshot,
} from "~/lib/identity-store";
import { buildUnsignedEvent } from "~/lib/design-publish/form-event-builder";
import {
  clearDraftFromSession,
  loadDraftFromSession,
  saveDraftToSession,
} from "~/lib/design-publish/form-draft";
import {
  getDesignNameFromUrl,
  getFormatFromUrl,
  getSuggestedMimeForFormat,
} from "~/lib/design-publish/form-inference";
import { renderPreviewImages } from "~/lib/design-publish/form-preview";
import { mapPublishHttpResult } from "~/lib/design-publish/publish";
import {
  type DesignPublishFormMode,
  DRAFT_FIELD_NAMES,
  INPUT_FIELD_NAMES,
  STEP_ORDER,
  type DraftInputs,
  type FieldElement,
  type FieldName,
  type IdentityMetadataDetail,
  type Inputs,
  type SignedNostrEvent,
  type SignerViewChangeDetail,
  type StepId,
  type StepPanelNodes,
} from "~/lib/design-publish/form-types";
import {
  FORMAT_RE,
  SHA256_RE,
  asHttpsUrl,
  generateDesignId,
  hasInvalidTextContent,
  normalizeSingleLine,
  normalizeTextArea,
  parseLineList,
  validateSignedEvent,
} from "~/lib/design-publish/form-utils";
import { isPubkey } from "~/lib/pubkey";

export const initDesignPublishForm = (rootOverride?: HTMLElement | null) => {
  const root =
    rootOverride ?? document.querySelector<HTMLElement>("[data-design-publish-form]");
  if (!root || root.dataset.initialized === "true") {
    return;
  }
  root.dataset.initialized = "true";

  const form = root.querySelector<HTMLFormElement>("[data-publish-form]");
  const signButton = root.querySelector<HTMLButtonElement>("[data-action='sign']");
  const publishButton = root.querySelector<HTMLButtonElement>("[data-action='publish']");
  const resetButton = root.querySelector<HTMLButtonElement>("[data-action='reset']");
  const signStatus = root.querySelector<HTMLElement>("[data-sign-status]");
  const validationSummary = root.querySelector<HTMLElement>("[data-validation-summary]");
  const unsignedOutput = root.querySelector<HTMLTextAreaElement>("[data-output='unsigned']");
  const signedOutput = root.querySelector<HTMLTextAreaElement>("[data-output='signed']");
  const hackerToggleButton = root.querySelector<HTMLButtonElement>(
    "[data-action='toggle-hacker']",
  );
  const hackerToggleLabel = root.querySelector<HTMLElement>("[data-hacker-toggle-label]");
  const hackerFields = Array.from(root.querySelectorAll<HTMLElement>("[data-hacker-field]"));
  const signerPill = root.querySelector<HTMLElement>("[data-step-signer-pill]");
  const signerPillText = root.querySelector<HTMLElement>("[data-step-signer-pill-text]");
  const signerPillDot = root.querySelector<HTMLElement>("[data-step-signer-dot]");
  const signerPanelHost = root.querySelector<HTMLElement>("[data-signer-panel]");
  const previewRenderList = root.querySelector<HTMLElement>("[data-preview-render-list]");

  const copyUnsignedBtn = root.querySelector<HTMLButtonElement>(
    "[data-action='copy-unsigned']",
  );
  const copySignedBtn = root.querySelector<HTMLButtonElement>("[data-action='copy-signed']");

  if (
    !form ||
    !signButton ||
    !publishButton ||
    !resetButton ||
    !signStatus ||
    !unsignedOutput ||
    !signedOutput ||
    !hackerToggleButton ||
    !hackerToggleLabel ||
    hackerFields.length === 0 ||
    !signerPillText ||
    !signerPillDot ||
    !copyUnsignedBtn ||
    !copySignedBtn
  ) {
    console.error("[design-publish-form] required DOM node missing");
    return;
  }

  const getInput = <T extends HTMLElement>(field: FieldName): T => {
    const node = root.querySelector<T>(`[data-field='${field}']`);
    if (!node) throw new Error(`Missing field node: ${field}`);
    return node;
  };

  const fields = {
    d: getInput<HTMLInputElement>("d"),
    previousVersionEventId: getInput<HTMLInputElement>("previousVersionEventId"),
    name: getInput<HTMLInputElement>("name"),
    format: getInput<HTMLSelectElement>("format"),
    url: getInput<HTMLInputElement>("url"),
    sha256: getInput<HTMLInputElement>("sha256"),
    description: getInput<HTMLTextAreaElement>("description"),
    preview: getInput<HTMLTextAreaElement>("preview"),
    category: getInput<HTMLTextAreaElement>("category"),
    material: getInput<HTMLTextAreaElement>("material"),
    printer: getInput<HTMLTextAreaElement>("printer"),
    license: getInput<HTMLInputElement>("license"),
    lnurl: getInput<HTMLInputElement>("lnurl"),
    mime: getInput<HTMLInputElement>("mime"),
  };
  const formatSelect = fields.format;

  const stepOrder: StepId[] = STEP_ORDER;
  const requiredForSign: StepId[] = ["signer", "file", "format", "name"];

  const stepIndexById = Object.fromEntries(
    stepOrder.map((step, index) => [step, index]),
  ) as Record<StepId, number>;

  const queryStepNode = <T extends HTMLElement>(attr: string, step: StepId): T | null =>
    root.querySelector<T>(`[${attr}='${step}']`);

  const buildStepPanels = (): Map<StepId, StepPanelNodes> | null => {
    const panels = new Map<StepId, StepPanelNodes>();
    let hasMissingNodes = false;

    for (const step of stepOrder) {
      const panel = queryStepNode<HTMLElement>("data-step-panel", step);
      const body = queryStepNode<HTMLElement>("data-step-body", step);
      const toggle = queryStepNode<HTMLButtonElement>("data-step-toggle", step);
      const summary = queryStepNode<HTMLElement>("data-step-summary", step);
      const backButton = queryStepNode<HTMLButtonElement>("data-step-back", step);
      const nextButton = queryStepNode<HTMLButtonElement>("data-step-next", step);
      const caretButton = queryStepNode<HTMLButtonElement>("data-step-caret", step);
      const caretIcon = queryStepNode<HTMLElement>("data-step-caret-icon", step);

      const missing: string[] = [];
      if (!panel) missing.push("panel");
      if (!body) missing.push("body");
      if (!toggle) missing.push("toggle");
      if (!caretButton) missing.push("caretButton");
      if (!caretIcon) missing.push("caretIcon");

      if (missing.length > 0) {
        hasMissingNodes = true;
        console.error(
          `[design-publish-form] missing step nodes for ${step}: ${missing.join(", ")}`,
        );
        continue;
      }

      const requiredPanel = panel as HTMLElement;
      const requiredBody = body as HTMLElement;
      const requiredToggle = toggle as HTMLButtonElement;
      const requiredCaretButton = caretButton as HTMLButtonElement;
      const requiredCaretIcon = caretIcon as HTMLElement;

      panels.set(step, {
        panel: requiredPanel,
        body: requiredBody,
        toggle: requiredToggle,
        summary,
        backButton,
        nextButton,
        caretButton: requiredCaretButton,
        caretIcon: requiredCaretIcon,
      });
    }

    if (hasMissingNodes) return null;
    return panels;
  };

  const stepPanels = buildStepPanels();
  if (!stepPanels) {
    console.error("[design-publish-form] step panel initialization failed");
    return;
  }

  const HACKER_MODE_STORAGE_KEY = "openprints:design-publish:hacker-mode";
  const apiBase = (root.getAttribute("data-api-base") ?? "").trim().replace(/\/$/, "");
  const rawMode = (root.getAttribute("data-form-mode") ?? "").trim().toLowerCase();
  const formMode: DesignPublishFormMode = rawMode === "edit" ? "edit" : "create";
  const lockedDesignId = normalizeSingleLine(root.getAttribute("data-locked-design-id") ?? "");
  const FORM_DRAFT_STORAGE_KEY =
    formMode === "edit"
      ? `openprints:design-publish:form-draft:edit:${encodeURIComponent(lockedDesignId || "unknown")}`
      : "openprints:design-publish:form-draft:create";
  const signIntentLabel = formMode === "edit" ? "update" : "design event";

  const parseInitialValues = (raw: string | null): Partial<Inputs> | null => {
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (!parsed || typeof parsed !== "object") return null;
      const values: Partial<Inputs> = {};
      for (const field of INPUT_FIELD_NAMES) {
        const value = (parsed as Record<string, unknown>)[field];
        if (typeof value === "string") {
          values[field] = value;
        }
      }
      return values;
    } catch {
      return null;
    }
  };

  const initialValues = parseInitialValues(root.getAttribute("data-initial-values"));
  let signerPubkey = "";
  let isSigning = false;
  let isPublishing = false;
  let isHackerMode = false;
  let signedEvent: SignedNostrEvent | null = null;
  let publishedSuccess = false;
  let activeStep: StepId | null = "signer";
  let autoMovedFromSigner = false;
  let signerIdentityText = "Signer";
  let signerChipLabel = "";
  let signerDotState: "hidden" | "blinking" | "solid" = "hidden";
  let lastPreviewRenderSignature = "";
  const manualCompleted = new Set<StepId>();

  const setStatus = (message: string) => {
    signStatus.textContent = message;
  };

  const setSummary = (message: string) => {
    if (validationSummary) validationSummary.textContent = message;
  };

  const setHackerMode = (enabled: boolean) => {
    isHackerMode = enabled;
    for (const el of hackerFields) {
      el.classList.toggle("hidden", !enabled);
    }
    hackerToggleButton.setAttribute("aria-expanded", String(enabled));
    hackerToggleLabel.textContent = enabled ? "Hide Nostr Data" : "Show Nostr Data";
    try {
      window.localStorage.setItem(HACKER_MODE_STORAGE_KEY, enabled ? "1" : "0");
    } catch {
      // no-op
    }
  };


  const getFieldElement = (field: FieldName): FieldElement => {
    if (field === "format") return formatSelect;
    return fields[field] as HTMLInputElement | HTMLTextAreaElement;
  };

  const getFieldValue = (field: FieldName): string => getFieldElement(field).value;

  const setFieldValue = (field: FieldName, value: string) => {
    getFieldElement(field).value = value;
  };

  const pickInputValues = <K extends FieldName>(names: readonly K[]): Pick<Inputs, K> => {
    const picked = {} as Pick<Inputs, K>;
    for (const name of names) {
      picked[name] = getFieldValue(name) as Inputs[K];
    }
    return picked;
  };

  const collectInputs = (): Inputs => {
    const inputs = pickInputValues(INPUT_FIELD_NAMES);
    if (formMode === "edit" && lockedDesignId) {
      inputs.d = lockedDesignId;
    }
    return inputs;
  };
  const collectDraftInputs = (): DraftInputs => pickInputValues(DRAFT_FIELD_NAMES);

  const applyDraft = (draft: DraftInputs | null) => {
    if (!draft) return;
    for (const field of DRAFT_FIELD_NAMES) {
      setFieldValue(field, draft[field]);
    }
  };

  const applyInitialValues = (values: Partial<Inputs> | null) => {
    if (!values) return;
    for (const field of INPUT_FIELD_NAMES) {
      const value = values[field];
      if (typeof value === "string") {
        setFieldValue(field, value);
      }
    }
  };

  let mimeTouched = false;
  let formatTouched = false;
  let nameTouched = false;
  const inferMimeButton = root.querySelector<HTMLButtonElement>("[data-action='infer-mime']");

  const getSuggestedMimeForCurrentFormat = (): string | undefined => {
    return getSuggestedMimeForFormat(formatSelect.value);
  };

  const refreshInferMimeVisibility = () => {
    if (!inferMimeButton) return;
    const suggested = getSuggestedMimeForCurrentFormat();
    const currentMime = normalizeSingleLine(fields.mime.value).toLowerCase();
    const shouldShow =
      mimeTouched &&
      !!suggested &&
      suggested.toLowerCase() !== currentMime &&
      currentMime.length > 0;
    inferMimeButton.classList.toggle("hidden", !shouldShow);
  };

  const maybePrefillMimeFromFormat = () => {
    if (mimeTouched) return;
    const suggested = getSuggestedMimeForCurrentFormat();
    if (!suggested) return;
    fields.mime.value = suggested;
    refreshInferMimeVisibility();
  };

  const maybeInferFormatFromUrl = () => {
    if (formatTouched) return;
    const inferred = getFormatFromUrl(fields.url.value);
    if (!inferred) return;
    if (formatSelect.value === inferred) return;
    formatSelect.value = inferred;
    maybePrefillMimeFromFormat();
  };

  const maybeInferNameFromUrl = () => {
    if (nameTouched) return;
    const current = normalizeSingleLine(fields.name.value);
    if (current.length > 0) return;
    const inferred = getDesignNameFromUrl(fields.url.value);
    if (!inferred) return;
    fields.name.value = inferred;
  };

  const maybePrefillLnurl = (lnurl: string | null | undefined) => {
    const current = fields.lnurl.value;
    if (current && current.trim().length > 0) return;
    if (!lnurl) return;
    const normalized = normalizeSingleLine(lnurl);
    if (!normalized) return;
    fields.lnurl.value = normalized;
    refreshUnsignedPreview();
  };

  const isSignerComplete = (): boolean => isPubkey(signerPubkey);
  const isNameComplete = (): boolean => {
    const name = normalizeSingleLine(fields.name.value);
    return name.length > 0 && name.length <= 120 && !hasInvalidTextContent(name);
  };
  const isFormatComplete = (): boolean => {
    const format = normalizeSingleLine(formatSelect.value).toLowerCase();
    const mime = normalizeSingleLine(fields.mime.value).toLowerCase();
    if (!format || !FORMAT_RE.test(format)) return false;
    if (mime && hasInvalidTextContent(mime)) return false;
    return true;
  };
  const isFileComplete = (): boolean => {
    const url = normalizeSingleLine(fields.url.value);
    const sha = normalizeSingleLine(fields.sha256.value).toLowerCase();
    return !!asHttpsUrl(url) && (!sha || SHA256_RE.test(sha));
  };

  const getCompletionState = (): Record<StepId, boolean> => ({
    signer: isSignerComplete(),
    name: isNameComplete(),
    format: isFormatComplete(),
    file: isFileComplete(),
    description: manualCompleted.has("description"),
    "additional-data": manualCompleted.has("additional-data"),
    "lightning-payments": manualCompleted.has("lightning-payments"),
    "design-images": manualCompleted.has("design-images"),
  });

  const getValidationState = (
    step: StepId,
    completion: Record<StepId, boolean>,
  ): "empty" | "valid" | "invalid" => {
    if (completion[step]) return "valid";
    if (step === "signer") return "empty";
    if (step === "name") {
      const value = normalizeSingleLine(fields.name.value);
      return value.length === 0 ? "empty" : "invalid";
    }
    if (step === "format") {
      const format = normalizeSingleLine(fields.format.value).toLowerCase();
      return format.length === 0 ? "empty" : "invalid";
    }
    if (step === "file") {
      const hasAny =
        normalizeSingleLine(fields.url.value).length > 0 ||
        normalizeSingleLine(fields.sha256.value).length > 0;
      return hasAny ? "invalid" : "empty";
    }
    if (step === "description") {
      return normalizeTextArea(fields.description.value).trim().length > 0 ? "valid" : "empty";
    }
    if (step === "additional-data") {
      const hasLicense = normalizeSingleLine(fields.license.value).length > 0;
      const hasCategories = parseLineList(fields.category.value).length > 0;
      const hasMaterials =
        parseLineList(fields.material.value).length > 0 ||
        parseLineList(fields.printer.value).length > 0;
      return hasLicense || hasCategories || hasMaterials ? "valid" : "empty";
    }
    if (step === "lightning-payments") {
      const hasLnurl = normalizeSingleLine(fields.lnurl.value).length > 0;
      return hasLnurl ? "valid" : "empty";
    }
    if (step === "design-images") {
      const hasImages = parseLineList(fields.preview.value).length > 0;
      return hasImages ? "valid" : "empty";
    }
    return "empty";
  };

  const getSummary = (step: StepId): string => {
    switch (step) {
      case "signer":
        return isSignerComplete() ? "Signer ready" : "Waiting for signer";
      case "name": {
        const value = normalizeSingleLine(fields.name.value);
        return value || "Name your design";
      }
      case "file": {
        const hasUrl = !!asHttpsUrl(normalizeSingleLine(fields.url.value));
        const hasSha = normalizeSingleLine(fields.sha256.value).length > 0;
        if (!hasUrl) return "Add a file URL";
        return hasSha ? "URL and SHA-256 set" : "URL set, no SHA-256";
      }
      case "format": {
        const format = normalizeSingleLine(formatSelect.value).toLowerCase();
        const mime = normalizeSingleLine(fields.mime.value).toLowerCase();
        if (!format) return "Choose the primary format";
        return mime ? `${format} (${mime})` : format;
      }
      case "description": {
        const text = normalizeTextArea(fields.description.value).trim();
        return text ? `${text.length} chars` : "No description";
      }
      case "additional-data": {
        const hasLicense = normalizeSingleLine(fields.license.value).length > 0;
        const categoryCount = parseLineList(fields.category.value).length;
        const materialCount = parseLineList(fields.material.value).length;
        const printerCount = parseLineList(fields.printer.value).length;
        const selected =
          Number(hasLicense) +
          Number(categoryCount > 0) +
          Number(materialCount > 0 || printerCount > 0);
        return selected > 0
          ? `${selected} section${selected === 1 ? "" : "s"} configured`
          : "Optional metadata";
      }
      case "lightning-payments": {
        const hasLnurl = normalizeSingleLine(fields.lnurl.value).length > 0;
        return hasLnurl ? "LNURL configured" : "No LNURL";
      }
      case "design-images": {
        const imageCount = parseLineList(fields.preview.value).length;
        return imageCount > 0
          ? `${imageCount} image URL${imageCount === 1 ? "" : "s"}`
          : "No preview images";
      }
    }
  };

  const refreshSignerIdentityText = () => {
    const detectedChip =
      signerChipLabel ||
      root.querySelector<HTMLElement>("[data-panel-pill-label]")?.textContent?.trim() ||
      "";
    if (detectedChip) {
      signerIdentityText = detectedChip;
    } else if (isSignerComplete()) {
      signerIdentityText = `${signerPubkey.slice(0, 10)}...${signerPubkey.slice(-6)}`;
    } else {
      signerIdentityText = "Signer";
    }
    if (signerPill) {
      signerPill.classList.toggle("hidden", !isSignerComplete());
      signerPillText.textContent = signerIdentityText;
    }

    const dotState =
      signerDotState ||
      (signerPanelHost?.dataset.signerDotState as
        | "hidden"
        | "blinking"
        | "solid"
        | undefined) ||
      "hidden";
    signerPillDot.classList.remove("signer-status-dot--blinking");
    if (dotState === "blinking") {
      signerPillDot.classList.remove("hidden");
      signerPillDot.classList.add("signer-status-dot--blinking");
    } else if (dotState === "solid") {
      signerPillDot.classList.remove("hidden");
    } else {
      signerPillDot.classList.add("hidden");
    }
  };

  const renderAccordion = () => {
    const completion = getCompletionState();

    for (const step of stepOrder) {
      const nodes = stepPanels.get(step);
      if (!nodes) continue;
      const validationState = getValidationState(step, completion);
      const open = step === activeStep;

      nodes.panel.dataset.validationState = validationState;
      nodes.panel.dataset.viewState = open ? "expanded" : "collapsed";
      nodes.body.classList.toggle("hidden", !open);
      nodes.caretIcon.classList.toggle("rotate-180", open);
      if (nodes.summary) nodes.summary.textContent = getSummary(step);
      nodes.toggle.disabled = false;
      nodes.toggle.classList.remove("opacity-60", "cursor-not-allowed");

      nodes.toggle.classList.toggle("hidden", open);
      nodes.toggle.classList.toggle("flex", !open);

      if (nodes.nextButton) {
        nodes.nextButton.disabled = false;
      }
    }

    refreshSignerIdentityText();
  };

  const openStep = (step: StepId) => {
    activeStep = step;
    renderAccordion();
  };

  const moveToNextStep = (step: StepId) => {
    const idx = stepIndexById[step];
    if (idx < 0 || idx >= stepOrder.length - 1) return;
    const next = stepOrder[idx + 1];
    openStep(next);
  };

  const moveToPreviousStep = (step: StepId) => {
    const idx = stepIndexById[step];
    if (idx <= 0) return;
    const previous = stepOrder[idx - 1];
    openStep(previous);
  };

  const maybeAutoAdvanceFromSigner = () => {
    if (isSignerComplete() && activeStep === "signer" && !autoMovedFromSigner) {
      activeStep = "file";
      autoMovedFromSigner = true;
    }
  };

  const refreshUnsignedPreview = () => {
    lastPreviewRenderSignature = renderPreviewImages(
      fields.preview.value,
      previewRenderList,
      lastPreviewRenderSignature,
    );
    maybeAutoAdvanceFromSigner();
    const result = buildUnsignedEvent(collectInputs(), signerPubkey);
    if (!result.ok) {
      unsignedOutput.value = "";
      setStatus(result.errors[0] ?? "Invalid form state.");
      setSummary("Waiting for signer and valid inputs.");
      signButton.disabled = true;
      publishButton.disabled = true;
      copyUnsignedBtn.disabled = true;
      renderAccordion();
      return;
    }

    unsignedOutput.value = JSON.stringify(result.event, null, 2);
    const warningText = result.warnings.length > 0 ? ` Warning: ${result.warnings.join(" ")}` : "";
    setSummary(`Unsigned event is valid and deterministic.${warningText}`);

    const completion = getCompletionState();
    const signUnlocked = requiredForSign.every((step) => completion[step]);
    signButton.disabled = isSigning || isPublishing || !signUnlocked;
    publishButton.disabled = !signedEvent || isPublishing;
    copyUnsignedBtn.disabled = unsignedOutput.value.length === 0;
    if (!signedEvent) setStatus(`Ready to sign. Click "Sign ${signIntentLabel}".`);

    renderAccordion();
  };

  const onIdentityMetadata = (event: Event) => {
    const customEvent = event as CustomEvent<IdentityMetadataDetail>;
    const detail = customEvent.detail;
    if (!detail) return;
    maybePrefillLnurl(detail.lnurl ?? null);
  };

  const onSignerViewChange = (event: Event) => {
    const customEvent = event as CustomEvent<SignerViewChangeDetail>;
    const detail = customEvent.detail;
    if (!detail) return;
    if (typeof detail.chipLabel === "string" && detail.chipLabel.trim().length > 0) {
      signerChipLabel = detail.chipLabel.trim();
    }
    if (
      detail.signedDot === "hidden" ||
      detail.signedDot === "blinking" ||
      detail.signedDot === "solid"
    ) {
      signerDotState = detail.signedDot;
    }
    maybeAutoAdvanceFromSigner();
    refreshSignerIdentityText();
  };


  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  };

  const handleCopyUnsigned = async () => {
    const text = unsignedOutput.value;
    if (!text) return;
    const ok = await copyText(text);
    setStatus(
      ok
        ? "Copied unsigned event JSON to clipboard."
        : "Copy failed. Your browser may block clipboard access.",
    );
  };

  const handleCopySigned = async () => {
    const text = signedOutput.value;
    if (!text) return;
    const ok = await copyText(text);
    setStatus(
      ok
        ? "Copied signed JSON to clipboard."
        : "Copy failed. Your browser may block clipboard access.",
    );
  };

  const clearSignedState = () => {
    signedEvent = null;
    publishedSuccess = false;
    signedOutput.value = "";
    copySignedBtn.disabled = true;
    publishButton.disabled = true;
  };

  const handleSign = async () => {
    if (isSigning || isPublishing) return;

    const completion = getCompletionState();
    const signUnlocked = requiredForSign.every((step) => completion[step]);
    if (!signUnlocked) {
      setStatus("Complete the previous steps before signing.");
      return;
    }

    const result = buildUnsignedEvent(collectInputs(), signerPubkey);
    if (!result.ok) {
      setStatus(result.errors[0] ?? "Cannot sign while form is invalid.");
      refreshUnsignedPreview();
      return;
    }

    isSigning = true;
    signButton.disabled = true;
    setStatus("Waiting for signer confirmation...");

    try {
      const signed = await signWithCurrentSigner<SignedNostrEvent>(result.event, {
        requirePubkeyMatch: true,
      });
      if (!validateSignedEvent(signed))
        throw new Error("Signer returned an invalid event shape.");

      signedEvent = signed;
      publishedSuccess = false;
      signedOutput.value = JSON.stringify(signed, null, 2);
      copySignedBtn.disabled = false;
      publishButton.disabled = false;
      setStatus("Event signed successfully. Continue to publish.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown signer error";
      setStatus(`Signing failed: ${message}`);
      clearSignedState();
    } finally {
      isSigning = false;
      refreshUnsignedPreview();
    }
  };

  const handlePublish = async () => {
    if (isPublishing || isSigning) return;
    if (!signedEvent) {
      setStatus("Sign an event before publishing.");
      return;
    }
    if (!apiBase) {
      setStatus("API base URL is not configured. Set PUBLIC_OPENPRINTS_API_URL.");
      return;
    }

    isPublishing = true;
    publishButton.disabled = true;
    signButton.disabled = true;
    setStatus("Sending signed event to indexer API...");

    try {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 20000);

      let response: Response;
      try {
        response = await fetch(`${apiBase}/designs/publish`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            accept: "application/json",
          },
          body: JSON.stringify(signedEvent),
          signal: controller.signal,
        });
      } finally {
        window.clearTimeout(timeout);
      }

      const payload = (await response.json().catch(() => null)) as unknown;
      const publishOutcome = mapPublishHttpResult(response.ok, response.status, payload);
      if (publishOutcome.kind === "failure") {
        const message = publishOutcome.message;
        setStatus(message);
        publishedSuccess = false;
        renderAccordion();
        return;
      }

      const accepted = publishOutcome.acceptedRelayCount;
      const duplicates = publishOutcome.duplicateRelayCount;
      const rejected = publishOutcome.rejectedRelayCount;
      publishedSuccess = true;
      setStatus(
        `Published to ${accepted} relay${accepted === 1 ? "" : "s"} (${duplicates} duplicate ack, ${rejected} rejected).`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown network error";
      publishedSuccess = false;
      setStatus(`Publish failed: ${message}`);
    } finally {
      isPublishing = false;
      const canSign = buildUnsignedEvent(collectInputs(), signerPubkey).ok;
      const completion = getCompletionState();
      signButton.disabled = !canSign || !requiredForSign.every((step) => completion[step]);
      publishButton.disabled = !signedEvent;
      renderAccordion();
    }
  };

  const handleReset = () => {
    form.reset();
    clearDraftFromSession(FORM_DRAFT_STORAGE_KEY);
    if (formMode === "edit") {
      applyInitialValues(initialValues);
      if (lockedDesignId) {
        fields.d.value = lockedDesignId;
      }
    } else {
      fields.d.value = generateDesignId();
    }
    mimeTouched = false;
    formatTouched = false;
    nameTouched = false;
    manualCompleted.clear();
    clearSignedState();
    autoMovedFromSigner = false;
    lastPreviewRenderSignature = "";
    activeStep = isSignerComplete() ? "file" : "signer";
    setStatus(
      formMode === "edit"
        ? "Edit form reset to current design values."
        : "Form reset. Complete each step to sign and publish.",
    );
    refreshUnsignedPreview();
    refreshInferMimeVisibility();
  };

  const handleStepNext = (step: StepId) => {
    if (
      step === "description" ||
      step === "additional-data" ||
      step === "lightning-payments" ||
      step === "design-images"
    ) {
      manualCompleted.add(step);
      renderAccordion();
    }

    moveToNextStep(step);
  };

  // init
  if (formMode === "edit") {
    applyInitialValues(initialValues);
    if (lockedDesignId) {
      fields.d.value = lockedDesignId;
    }
  } else {
    fields.d.value = generateDesignId();
  }
  applyDraft(loadDraftFromSession(FORM_DRAFT_STORAGE_KEY));
  if (formMode === "edit" && lockedDesignId) {
    fields.d.value = lockedDesignId;
  }

  const allWatchFields: (HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement)[] =
    INPUT_FIELD_NAMES
      .filter((field) => field !== "d" && field !== "previousVersionEventId")
      .map((field) => getFieldElement(field));

  for (const field of allWatchFields) {
    const onChange = () => {
      if (signedEvent) clearSignedState();
      refreshUnsignedPreview();
      refreshInferMimeVisibility();
      saveDraftToSession(FORM_DRAFT_STORAGE_KEY, collectDraftInputs());
    };
    field.addEventListener("input", onChange);
    field.addEventListener("change", onChange);
  }

  const mimeField = fields.mime as HTMLInputElement;
  const formatField = formatSelect;
  const urlField = fields.url as HTMLInputElement;
  const nameField = fields.name as HTMLInputElement;

  mimeField.addEventListener("input", () => {
    mimeTouched = true;
    refreshInferMimeVisibility();
  });

  nameField.addEventListener("input", () => {
    nameTouched = true;
  });

  formatField.addEventListener("change", () => {
    formatTouched = true;
    maybePrefillMimeFromFormat();
    refreshInferMimeVisibility();
    saveDraftToSession(FORM_DRAFT_STORAGE_KEY, collectDraftInputs());
  });

  urlField.addEventListener("change", () => {
    maybeInferFormatFromUrl();
    maybeInferNameFromUrl();
    refreshUnsignedPreview();
    saveDraftToSession(FORM_DRAFT_STORAGE_KEY, collectDraftInputs());
  });

  inferMimeButton?.addEventListener("click", () => {
    const suggested = getSuggestedMimeForCurrentFormat();
    if (!suggested) return;
    fields.mime.value = suggested;
    mimeTouched = false;
    refreshUnsignedPreview();
    refreshInferMimeVisibility();
    saveDraftToSession(FORM_DRAFT_STORAGE_KEY, collectDraftInputs());
  });

  for (const step of stepOrder) {
    const nodes = stepPanels.get(step);
    if (!nodes) continue;
    nodes.toggle.addEventListener("click", () => openStep(step));
    nodes.backButton?.addEventListener("click", () => moveToPreviousStep(step));
    nodes.nextButton?.addEventListener("click", () => handleStepNext(step));
    nodes.caretButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      activeStep = activeStep === step ? null : step;
      renderAccordion();
    });
  }

  signButton.addEventListener("click", () => void handleSign());
  publishButton.addEventListener("click", () => void handlePublish());
  resetButton.addEventListener("click", handleReset);

  copyUnsignedBtn.addEventListener("click", () => void handleCopyUnsigned());
  copySignedBtn.addEventListener("click", () => void handleCopySigned());

  hackerToggleButton.addEventListener("click", () => setHackerMode(!isHackerMode));

  document.addEventListener("openprints-identity-metadata", onIdentityMetadata);
  document.addEventListener("openprints-signer-view-change", onSignerViewChange);

  startIdentityStore();
  const unsubscribeIdentityStore = subscribeToCurrentIdentity((snapshot: IdentitySnapshot) => {
    signerPubkey = snapshot.pubkey && snapshot.authoritative ? snapshot.pubkey : "";
    maybePrefillLnurl(
      snapshot.identity?.lnurl ?? snapshot.identity?.lud16 ?? snapshot.identity?.lud06 ?? null,
    );
    maybeAutoAdvanceFromSigner();
    refreshUnsignedPreview();
  });

  try {
    setHackerMode(window.localStorage.getItem(HACKER_MODE_STORAGE_KEY) === "1");
  } catch {
    setHackerMode(false);
  }

  activeStep = isSignerComplete() ? "file" : "signer";
  refreshUnsignedPreview();
  if (signerPubkey) {
    setStatus("Signer detected. Continue with the next step.");
  } else {
    setStatus("Waiting for signer pubkey...");
  }
  renderAccordion();

  window.addEventListener(
    "beforeunload",
    () => {
      unsubscribeIdentityStore();
    },
    { once: true },
  );
};
