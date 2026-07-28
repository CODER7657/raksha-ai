-- Adds scam category tracking so we can build a real (not fake) trending
-- scam feed from actual aggregate scan data, instead of raw content.

alter table public.scans add column if not exists category text;

-- Cross-user aggregate: what categories are trending recently. Deliberately
-- does NOT return any input_text or user_id — category + count only, so
-- this is safe to expose to any authenticated user without leaking anyone's
-- specific message content.
create or replace function get_trending_categories(days_back int default 7, result_limit int default 8)
returns table (category text, occurrences bigint)
language sql stable
as $$
  select category, count(*) as occurrences
  from public.scans
  where category is not null
    and category <> 'none'
    and created_at > now() - (days_back || ' days')::interval
  group by category
  order by occurrences desc
  limit result_limit;
$$;
