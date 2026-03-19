import {
  mapUnknownDesignDetailToDetailModel,
  mapUnknownDesignVersions,
  type ValidDesignDetail,
  type ValidDesignVersion,
} from "~/lib/designs";

const DEFAULT_VERSIONS_PAGE_SIZE = 30;
const LOOKUP_VERSIONS_PAGE_SIZE = 100;

type HistoricalContext =
  | {
      requestedVersionId: string;
      versionNumber: number | null;
      versionTimestamp: number | null;
      latestHref: string;
    }
  | null;

export interface LoadDesignVersionViewDataResult {
  design: ValidDesignDetail | null;
  versions: ValidDesignVersion[];
  versionsTotal: number;
  versionsError: string | null;
  selectedVersion: ValidDesignVersion | null;
  isHistoricalView: boolean;
  historicalContext: HistoricalContext;
  errorTitle: string | null;
  errorMessage: string | null;
}

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
  const isHistoricalView = normalizedRequestedVersionId != null;

  if (!base) {
    return {
      design: null,
      versions: [],
      versionsTotal: 0,
      versionsError: null,
      selectedVersion: null,
      isHistoricalView,
      historicalContext: null,
      errorTitle: "Design not available",
      errorMessage:
        "API base URL is not configured. Check PUBLIC_OPENPRINTS_API_URL.",
    };
  }

  if (!normalizedDesignId) {
    return {
      design: null,
      versions: [],
      versionsTotal: 0,
      versionsError: null,
      selectedVersion: null,
      isHistoricalView,
      historicalContext: null,
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
        design: null,
        versions: [],
        versionsTotal: 0,
        versionsError: null,
        selectedVersion: null,
        isHistoricalView,
        historicalContext: null,
        errorTitle: "Design not found",
        errorMessage: `API responded with ${res.status} ${res.statusText} for this design.`,
      };
    }

    const mapped = mapUnknownDesignDetailToDetailModel(await res.json());
    if (mapped.kind === "invalid") {
      return {
        design: null,
        versions: [],
        versionsTotal: 0,
        versionsError: null,
        selectedVersion: null,
        isHistoricalView,
        historicalContext: null,
        errorTitle: "Design unavailable",
        errorMessage: mapped.reason,
      };
    }

    design = mapped;
  } catch {
    return {
      design: null,
      versions: [],
      versionsTotal: 0,
      versionsError: null,
      selectedVersion: null,
      isHistoricalView,
      historicalContext: null,
      errorTitle: "Design not found",
      errorMessage:
        "We couldn't load this design due to a network or server error.",
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
  let versionsError = firstPage.error;

  let selectedVersion = versions[0] ?? null;
  let selectedVersionIndex = versions.length > 0 ? 0 : null;

  if (isHistoricalView && normalizedRequestedVersionId) {
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
            versionsError = page.error;
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

  if (isHistoricalView && !selectedVersion) {
    return {
      design,
      versions,
      versionsTotal,
      versionsError,
      selectedVersion: null,
      isHistoricalView: true,
      historicalContext: null,
      errorTitle: "Version not found",
      errorMessage:
        "The requested version could not be found for this design.",
    };
  }

  const versionNumber =
    selectedVersionIndex != null && versionsTotal > 0
      ? Math.max(1, versionsTotal - selectedVersionIndex)
      : null;

  return {
    design,
    versions,
    versionsTotal,
    versionsError,
    selectedVersion,
    isHistoricalView,
    historicalContext:
      isHistoricalView && normalizedRequestedVersionId
        ? {
            requestedVersionId: normalizedRequestedVersionId,
            versionNumber,
            versionTimestamp: selectedVersion?.created_at ?? null,
            latestHref: buildDesignLatestHref(normalizedDesignId),
          }
        : null,
    errorTitle: null,
    errorMessage: null,
  };
};
