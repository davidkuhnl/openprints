export type {
  ApiCreatorIdentity,
  ApiDesignDetail,
  ApiDesignDetailParseResult,
  ApiDesignListItem,
  ApiDesignListItemParseResult,
  ApiDesignStats,
  ApiDesignStatsParseResult,
} from "~/lib/designs/api";
export {
  parseApiDesignDetail,
  parseApiDesignListItem,
  parseApiDesignListItems,
  parseApiDesignStats,
} from "~/lib/designs/api";

export type {
  CreatorIdentityCard,
  CreatorIdentityDetail,
  DesignCardModel,
  DesignDetailModel,
  DesignDetailEndorsement,
  DesignDetailZap,
  InvalidDesignCard,
  InvalidDesignDetail,
  ValidDesignCard,
  ValidDesignDetail,
} from "~/lib/designs/view";

export {
  mapApiDesignListItemToCardModel,
  mapApiDesignDetailToDetailModel,
  mapApiDesignParseResultToCardModel,
  mapUnknownDesignDetailToDetailModel,
  mapUnknownDesignListToCardModels,
  mapUnknownDesignStats,
} from "~/lib/designs/mappers";
