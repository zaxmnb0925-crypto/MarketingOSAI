export type Brand = {
  id: string;
  workspace_id: string;
  name: string;
  industry: string | null;
  website: string | null;
  description: string | null;
  tone: string | null;
  target_audience: string | null;
  brand_voice: string | null;
  value_proposition: string | null;
  products_services: string | null;
  keywords: string | null;
  forbidden_words: string | null;
  default_cta: string | null;
  language: string | null;
  country: string | null;
  brand_guidelines: string | null;
};

export type BrandForm = {
  name: string;
  industry: string;
  website: string;
  description: string;
  tone: string;
  target_audience: string;
  brand_voice: string;
  value_proposition: string;
  products_services: string;
  keywords: string;
  forbidden_words: string;
  default_cta: string;
  language: string;
  country: string;
  brand_guidelines: string;
};

export function brandToForm(
  brand: Brand,
): BrandForm {
  return {
    name: brand.name || "",
    industry: brand.industry || "",
    website: brand.website || "",
    description: brand.description || "",
    tone: brand.tone || "",
    target_audience:
      brand.target_audience || "",
    brand_voice:
      brand.brand_voice || "",
    value_proposition:
      brand.value_proposition || "",
    products_services:
      brand.products_services || "",
    keywords: brand.keywords || "",
    forbidden_words:
      brand.forbidden_words || "",
    default_cta:
      brand.default_cta || "",
    language:
      brand.language || "zh-TW",
    country:
      brand.country || "Taiwan",
    brand_guidelines:
      brand.brand_guidelines || "",
  };
}
