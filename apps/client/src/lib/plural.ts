const pluralRules = new Intl.PluralRules("en");

type PluralForms = {
  one: string;
  other: string;
};

export function nounForCount(count: number, forms: PluralForms): string {
  const category = pluralRules.select(count);
  return category === "one" ? forms.one : forms.other;
}

