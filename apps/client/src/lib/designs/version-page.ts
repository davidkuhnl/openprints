import {
  mapUnknownDesignDetailToDetailModel,
  mapUnknownDesignVersions,
  type ValidDesignDetail,
  type ValidDesignVersion,
} from "~/lib/designs";

const DEFAULT_VERSIONS_PAGE_SIZE = 30;
const LOOKUP_VERSIONS_PAGE_SIZE = 100;

export interface DesignVersionViewContext {
  mode: "latest" | "historical";
  requestedVersionId: string | null;
  versionNumber: number | null;
  versionTimestamp: number | null;
  latestHref: string;
}

interface LoadDesignVersionViewDataValidBaseResult {
  kind: "valid";
  design: ValidDesignDetail;
  versions: ValidDesignVersion[];
  versionsTotal: number;
  selectedVersion: ValidDesignVersion;
  viewContext: DesignVersionViewContext;
}

export type LoadDesignVersionViewDataValidResult = LoadDesignVersionViewDataValidBaseResult;

export interface LoadDesignVersionViewDataErrorResult {
  kind: "error";
  viewContext: DesignVersionViewContext;
  errorTitle: string;
  errorMessage: string;
}

export type LoadDesignVersionViewDataResult =
  | LoadDesignVersionViewDataValidResult
  | LoadDesignVersionViewDataErrorResult;

interface LoadDesignVersionViewDataInput {
  apiBaseUrl: string;
  designId: string | undefined;
  requestedVersionId?: string | null;
}

interface FetchVersionsPageResult {
  ok: boolean;
  items: ValidDesignVersion[];
  total: number;
  limit: number;
  offset: number;
  error: string | null;
}

const trimToNull = (value: string | null | undefined): string | null => {
  const trimmed = value?.trim() ?? "";
  return trimmed.length > 0 ? trimmed : null;
};

const normalizeApiBase = (apiBaseUrl: string): string | null => {
  const trimmed = apiBaseUrl.trim();
  return trimmed.length > 0 ? trimmed.replace(/\/$/, "") : null;
};

const buildDesignLatestHref = (designId: string): string =>
  `/app/designs/${encodeURIComponent(designId)}`;

const buildViewContext = ({
  designId,
  requestedVersionId,
  versionNumber = null,
  versionTimestamp = null,
}: {
  designId: string | null;
  requestedVersionId: string | null;
  versionNumber?: number | null;
  versionTimestamp?: number | null;
}): DesignVersionViewContext => ({
  mode: requestedVersionId ? "historical" : "latest",
  requestedVersionId,
  versionNumber,
  versionTimestamp,
  latestHref: designId ? buildDesignLatestHref(designId) : "/app/designs",
});

const fetchVersionsPage = async (
  base: string,
  designId: string,
  limit: number,
  offset: number,
): Promise<FetchVersionsPageResult> => {
  const url = `${base}/designs/${encodeURIComponent(designId)}/versions?limit=${limit}&offset=${offset}`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      return {
        ok: false,
        items: [],
        total: 0,
        limit,
        offset,
        error: `Version history unavailable (${res.status} ${res.statusText}).`,
      };
    }

    const mapped = mapUnknownDesignVersions(await res.json());
    return {
      ok: true,
      items: mapped.items,
      total: mapped.total,
      limit: mapped.limit,
      offset: mapped.offset,
      error: null,
    };
  } catch {
    return {
      ok: false,
      items: [],
      total: 0,
      limit,
      offset,
      error: "Version history couldn't be loaded due to a network or server error.",
    };
  }
};

export const loadDesignVersionViewData = async ({
  apiBaseUrl,
  designId,
  requestedVersionId,
}: LoadDesignVersionViewDataInput): Promise<LoadDesignVersionViewDataResult> => {
  const base = normalizeApiBase(apiBaseUrl);
  const normalizedDesignId = trimToNull(designId);
  const normalizedRequestedVersionId = trimToNull(requestedVersionId);
  const baseViewContext = buildViewContext({
    designId: normalizedDesignId,
    requestedVersionId: normalizedRequestedVersionId,
  });

  if (!base) {
    return {
      kind: "error",
      viewContext: baseViewContext,
      errorTitle: "Design not available",
      errorMessage:
        "API base URL is not configured. Check PUBLIC_OPENPRINTS_API_URL.",
    };
  }

  if (!normalizedDesignId) {
    return {
      kind: "error",
      viewContext: baseViewContext,
      errorTitle: "Design not found",
      errorMessage: "Missing design id in the URL.",
    };
  }

  const designUrl = `${base}/designs/${encodeURIComponent(normalizedDesignId)}`;
  let design: ValidDesignDetail | null = null;

  try {
    const res = await fetch(designUrl);
    if (!res.ok) {
      return {
        kind: "error",
        viewContext: baseViewContext,
        errorTitle: "Design not found",
        errorMessage: `API responded with ${res.status} ${res.statusText} for this design.`,
      };
    }

    const mapped = mapUnknownDesignDetailToDetailModel(await res.json());
    if (mapped.kind === "invalid") {
      return {
        kind: "error",
        viewContext: baseViewContext,
        errorTitle: "Design unavailable",
        errorMessage: mapped.reason,
      };
    }

    design = mapped;
  } catch {
    return {
      kind: "error",
      viewContext: baseViewContext,
      errorTitle: "Design not found",
      errorMessage:
        "We couldn't load this design due to a network or server error.",
    };
  }

  if (!design) {
    return {
      kind: "error",
      viewContext: baseViewContext,
      errorTitle: "Design unavailable",
      errorMessage: "This design could not be loaded.",
    };
  }

  const firstPage = await fetchVersionsPage(
    base,
    normalizedDesignId,
    DEFAULT_VERSIONS_PAGE_SIZE,
    0,
  );
  const versions = firstPage.items;
  const versionsTotal = firstPage.total;

  let selectedVersion = versions[0] ?? null;
  let selectedVersionIndex = versions.length > 0 ? 0 : null;

  if (normalizedRequestedVersionId) {
    const firstPageMatchIndex = versions.findIndex(
      (item) => item.event_id === normalizedRequestedVersionId,
    );

    if (firstPageMatchIndex >= 0) {
      selectedVersion = versions[firstPageMatchIndex] ?? null;
      selectedVersionIndex = firstPageMatchIndex;
    } else {
      selectedVersion = null;
      selectedVersionIndex = null;

      // Fall back to pagination search if version is not in the default timeline window.
      if (firstPage.ok && versionsTotal > versions.length) {
        let offset = firstPage.offset + Math.max(1, firstPage.limit);
        while (offset < versionsTotal) {
          const page = await fetchVersionsPage(
            base,
            normalizedDesignId,
            LOOKUP_VERSIONS_PAGE_SIZE,
            offset,
          );

          if (!page.ok) {
            break;
          }

          const pageMatchIndex = page.items.findIndex(
            (item) => item.event_id === normalizedRequestedVersionId,
          );
          if (pageMatchIndex >= 0) {
            selectedVersion = page.items[pageMatchIndex] ?? null;
            selectedVersionIndex = offset + pageMatchIndex;
            break;
          }

          const pageStep = Math.max(1, page.items.length, page.limit);
          if (page.items.length === 0) {
            break;
          }
          offset += pageStep;
        }
      }
    }
  }

  if (normalizedRequestedVersionId && !selectedVersion) {
    return {
      kind: "error",
      viewContext: buildViewContext({
        designId: normalizedDesignId,
        requestedVersionId: normalizedRequestedVersionId,
      }),
      errorTitle: "Version not found",
      errorMessage:
        "The requested version could not be found for this design.",
    };
  }

  if (!selectedVersion) {
    return {
      kind: "error",
      viewContext: buildViewContext({
        designId: normalizedDesignId,
        requestedVersionId: normalizedRequestedVersionId,
      }),
      errorTitle: "Version unavailable",
      errorMessage: "No version data is available for this design.",
    };
  }

  const versionNumber =
    selectedVersionIndex != null && versionsTotal > 0
      ? Math.max(1, versionsTotal - selectedVersionIndex)
      : null;

  return {
    kind: "valid",
    design,
    versions,
    versionsTotal,
    selectedVersion,
    viewContext: buildViewContext({
      designId: normalizedDesignId,
      requestedVersionId: normalizedRequestedVersionId,
      versionNumber,
      versionTimestamp: selectedVersion.created_at ?? null,
    }),
  };
};
