-- =====================================================================
-- AgriSphere AI — Row Level Security policies
-- Users can only ever touch their own rows through anon/authenticated
-- keys. The backend uses the service-role key and bypasses RLS.
-- =====================================================================

alter table users enable row level security;
alter table farms enable row level security;
alter table recommendations enable row level security;
alter table disease_reports enable row level security;
alter table profit_predictions enable row level security;
alter table market_predictions enable row level security;
alter table weather_records enable row level security;
alter table chat_sessions enable row level security;
alter table chat_messages enable row level security;
alter table notifications enable row level security;
alter table activities enable row level security;
alter table agent_logs enable row level security;

-- users: self access
create policy "users_select_own" on users
  for select using (auth.uid() = id);
create policy "users_update_own" on users
  for update using (auth.uid() = id) with check (auth.uid() = id);

-- generic per-user policies
create policy "farms_all_own" on farms
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "recommendations_all_own" on recommendations
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "disease_reports_all_own" on disease_reports
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "profit_predictions_all_own" on profit_predictions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "market_predictions_all_own" on market_predictions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "weather_records_all_own" on weather_records
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "chat_sessions_all_own" on chat_sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "chat_messages_all_own" on chat_messages
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "notifications_select_own" on notifications
  for select using (auth.uid() = user_id);
create policy "notifications_update_own" on notifications
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "activities_all_own" on activities
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- agent_logs: backend-only (service role bypasses RLS; no anon policy)

-- =====================================================================
-- Storage bucket: disease-images (public read, owner-scoped writes)
-- =====================================================================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'disease-images', 'disease-images', true, 10485760,
  array['image/jpeg','image/png','image/webp','image/heic']
)
on conflict (id) do nothing;

create policy "disease_images_public_read" on storage.objects
  for select using (bucket_id = 'disease-images');

create policy "disease_images_owner_write" on storage.objects
  for insert with check (
    bucket_id = 'disease-images'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "disease_images_owner_delete" on storage.objects
  for delete using (
    bucket_id = 'disease-images'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- ---------------------------------------------------------------------
-- mandis + vendors: public directory, readable by any authenticated user;
-- writes are backend-only (service role bypasses RLS).
-- ---------------------------------------------------------------------
alter table mandis enable row level security;
alter table vendors enable row level security;

create policy "mandis_select_authenticated" on mandis
  for select to authenticated using (true);

create policy "vendors_select_authenticated" on vendors
  for select to authenticated using (true);
