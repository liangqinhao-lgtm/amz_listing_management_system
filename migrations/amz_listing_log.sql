create table public.amz_listing_log (
  id integer primary key not null default nextval('amz_listing_log_id_seq'::regclass),
  meow_sku character varying(255) not null, -- 我们内部的、被发布的子体SKU
  parent_sku character varying(255) not null, -- 该子体被关联到的父体SKU
  variation_attributes jsonb, -- 一个JSON对象，存储该子体具体的变体属性，例如: {"color_name": "Red", "size_name": "L"}
  listing_batch_id uuid not null, -- 用于标识同一次发品操作的唯一批次ID
  status character varying(50) not null default 'GENERATED',
  created_at timestamp with time zone not null default CURRENT_TIMESTAMP,
  variation_theme character varying(255) -- 该变体家族的变体主题，例如: Color-Size。用于在增补新成员时，指导LLM提取正确的属性。
);
create unique index amz_listing_log_meow_sku_key on amz_listing_log using btree (meow_sku);
create index idx_amz_listing_log_parent_sku on amz_listing_log using btree (parent_sku);
comment on table public.amz_listing_log is '记录亚马逊发品操作的日志表，用于追踪父子关系和变体属性';
comment on column public.amz_listing_log.meow_sku is '我们内部的、被发布的子体SKU';
comment on column public.amz_listing_log.parent_sku is '该子体被关联到的父体SKU';
comment on column public.amz_listing_log.variation_attributes is '一个JSON对象，存储该子体具体的变体属性，例如: {"color_name": "Red", "size_name": "L"}';
comment on column public.amz_listing_log.listing_batch_id is '用于标识同一次发品操作的唯一批次ID';
comment on column public.amz_listing_log.variation_theme is '该变体家族的变体主题，例如: Color-Size。用于在增补新成员时，指导LLM提取正确的属性。';

