-- Recommended indexes for All Listings endpoints.
-- Apply manually in production after review. This repo currently does not run Alembic migrations automatically.

-- Date range filters and collected-time sort
CREATE INDEX IF NOT EXISTS ix_marketplace_results_research_date
ON public.marketplace_research_results (research_date);

CREATE INDEX IF NOT EXISTS ix_marketplace_results_collected_at_desc
ON public.marketplace_research_results (collected_at DESC);

-- Exact-match filters used by All Listings
CREATE INDEX IF NOT EXISTS ix_marketplace_results_listing_status_norm
ON public.marketplace_research_results ((lower(trim(coalesce(listing_status, '')))));

CREATE INDEX IF NOT EXISTS ix_marketplace_results_brand_norm
ON public.marketplace_research_results ((lower(trim(coalesce(brand, '')))));

CREATE INDEX IF NOT EXISTS ix_marketplace_results_model_norm
ON public.marketplace_research_results ((lower(trim(coalesce(model, '')))));

CREATE INDEX IF NOT EXISTS ix_marketplace_results_condition_norm
ON public.marketplace_research_results ((lower(trim(coalesce("condition", '')))));

CREATE INDEX IF NOT EXISTS ix_marketplace_results_category_name_norm
ON public.marketplace_research_results ((lower(trim(coalesce(category_name, '')))));

-- Optional trigram indexes for ILIKE search. Requires pg_trgm extension.
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS ix_marketplace_results_listing_title_trgm
ON public.marketplace_research_results USING gin (listing_title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_marketplace_results_listing_id_trgm
ON public.marketplace_research_results USING gin (listing_id gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_marketplace_results_seller_or_shop_trgm
ON public.marketplace_research_results USING gin (seller_or_shop gin_trgm_ops);
