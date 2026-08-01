from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, MetaData, String, Table, Text


metadata = MetaData()


marketplace_research_results = Table(
    "marketplace_research_results",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("marketplace", String(64), nullable=False, index=True),
    Column("listing_id", String(255), nullable=False, index=True),
    Column("listing_title", Text, nullable=False),
    Column("listing_url", Text, nullable=True),
    Column("image_url", Text, nullable=True),
    Column("seller_or_shop", Text, nullable=True),
    Column("price", Float, nullable=True),
    Column("shipping_price", Float, nullable=True),
    Column("total_price", Float, nullable=True),
    Column("currency", String(16), nullable=True),
    Column("quantity", Integer, nullable=True),
    Column("count", Integer, nullable=True),
    Column("listing_status", String(32), nullable=True),
    Column("brand", Text, nullable=True),
    Column("model", Text, nullable=True),
    Column("listing_location", Text, nullable=True),
    Column("listing_views", Integer, nullable=True),
    Column("condition", Text, nullable=True),
    Column("category", Text, nullable=True),
    Column("category_name", Text, nullable=True),
    Column("buying_options", Text, nullable=True),
    Column("research_date", Date, nullable=True),
    Column("collected_at", DateTime, nullable=True),
    Column("updated_at", DateTime, nullable=True, index=True),
    Column("exclude_flag", Boolean, nullable=True),
    schema="public",
)