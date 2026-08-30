create schema if not exists private;

revoke all on schema private from public;
grant usage on schema private to authenticated;

create or replace function private.is_campaign_member(target_campaign_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.campaign_members
        where campaign_id = target_campaign_id
          and user_id = (select auth.uid())
    );
$$;

create or replace function private.is_campaign_owner(target_campaign_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.campaigns
        where id = target_campaign_id
          and owner_id = (select auth.uid())
    );
$$;

create or replace function private.can_manage_campaign(target_campaign_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.campaign_members
        where campaign_id = target_campaign_id
          and user_id = (select auth.uid())
          and role in ('owner', 'gm')
    );
$$;

create or replace function private.shares_campaign_with(other_user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.campaign_members own_membership
        join public.campaign_members other_membership
          on other_membership.campaign_id = own_membership.campaign_id
        where own_membership.user_id = (select auth.uid())
          and other_membership.user_id = other_user_id
    );
$$;

create or replace function private.can_access_character(target_character_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.characters character
        join public.campaign_members membership
          on membership.campaign_id = character.campaign_id
        where character.id = target_character_id
          and membership.user_id = (select auth.uid())
    );
$$;

create or replace function private.can_manage_character(target_character_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.characters character
        left join public.campaign_members membership
          on membership.campaign_id = character.campaign_id
         and membership.user_id = (select auth.uid())
        where character.id = target_character_id
          and (
              character.user_id = (select auth.uid())
              or membership.role in ('owner', 'gm')
          )
    );
$$;

revoke all on function private.is_campaign_member(uuid) from public;
revoke all on function private.is_campaign_owner(uuid) from public;
revoke all on function private.can_manage_campaign(uuid) from public;
revoke all on function private.shares_campaign_with(uuid) from public;
revoke all on function private.can_access_character(uuid) from public;
revoke all on function private.can_manage_character(uuid) from public;

grant execute on function private.is_campaign_member(uuid) to authenticated;
grant execute on function private.is_campaign_owner(uuid) to authenticated;
grant execute on function private.can_manage_campaign(uuid) to authenticated;
grant execute on function private.shares_campaign_with(uuid) to authenticated;
grant execute on function private.can_access_character(uuid) to authenticated;
grant execute on function private.can_manage_character(uuid) to authenticated;

revoke all on function public.set_updated_at() from public;
revoke all on function public.create_profile_for_new_user() from public;
revoke all on function public.add_campaign_owner_membership() from public;
revoke all on function public.prevent_campaign_owner_change() from public;
revoke all on function public.is_valid_dice_spec(jsonb) from public;
grant execute on function public.is_valid_dice_spec(jsonb) to authenticated, service_role;

alter table public.profiles enable row level security;
alter table public.campaigns enable row level security;
alter table public.campaign_members enable row level security;
alter table public.characters enable row level security;
alter table public.scenes enable row level security;
alter table public.entities enable row level security;
alter table public.inventory_items enable row level security;
alter table public.pending_checks enable row level security;
alter table public.game_events enable row level security;

revoke all on table public.profiles from anon, authenticated;
revoke all on table public.campaigns from anon, authenticated;
revoke all on table public.campaign_members from anon, authenticated;
revoke all on table public.characters from anon, authenticated;
revoke all on table public.scenes from anon, authenticated;
revoke all on table public.entities from anon, authenticated;
revoke all on table public.inventory_items from anon, authenticated;
revoke all on table public.pending_checks from anon, authenticated;
revoke all on table public.game_events from anon, authenticated;

grant select on table public.profiles to authenticated;
grant update (display_name) on table public.profiles to authenticated;

grant select, insert, delete on table public.campaigns to authenticated;
grant update (title, status, current_scene_id) on table public.campaigns to authenticated;

grant select, insert, delete on table public.campaign_members to authenticated;
grant update (role) on table public.campaign_members to authenticated;

grant select, insert, delete on table public.characters to authenticated;
grant update (name, hp, status) on table public.characters to authenticated;

grant select, insert, delete on table public.scenes to authenticated;
grant update (name, description, state) on table public.scenes to authenticated;

grant select, insert, delete on table public.entities to authenticated;
grant update (entity_type, name, description, state) on table public.entities
to authenticated;

grant select, insert, delete on table public.inventory_items to authenticated;
grant update (item_type, name, quantity, state) on table public.inventory_items
to authenticated;

grant select, insert, delete on table public.pending_checks to authenticated;
grant update (status, resolved_at) on table public.pending_checks to authenticated;

grant select, insert on table public.game_events to authenticated;

grant all on table public.profiles to service_role;
grant all on table public.campaigns to service_role;
grant all on table public.campaign_members to service_role;
grant all on table public.characters to service_role;
grant all on table public.scenes to service_role;
grant all on table public.entities to service_role;
grant all on table public.inventory_items to service_role;
grant all on table public.pending_checks to service_role;
grant all on table public.game_events to service_role;

create policy profiles_select_shared_campaign
on public.profiles
for select
to authenticated
using (
    id = (select auth.uid())
    or (select private.shares_campaign_with(id))
);

create policy profiles_update_self
on public.profiles
for update
to authenticated
using (id = (select auth.uid()))
with check (id = (select auth.uid()));

create policy campaigns_select_member
on public.campaigns
for select
to authenticated
using ((select private.is_campaign_member(id)));

create policy campaigns_insert_owner
on public.campaigns
for insert
to authenticated
with check (owner_id = (select auth.uid()));

create policy campaigns_update_manager
on public.campaigns
for update
to authenticated
using ((select private.can_manage_campaign(id)))
with check ((select private.can_manage_campaign(id)));

create policy campaigns_delete_owner
on public.campaigns
for delete
to authenticated
using ((select private.is_campaign_owner(id)));

create policy campaign_members_select_member
on public.campaign_members
for select
to authenticated
using ((select private.is_campaign_member(campaign_id)));

create policy campaign_members_insert_owner
on public.campaign_members
for insert
to authenticated
with check (
    (select private.is_campaign_owner(campaign_id))
    and role in ('player', 'gm')
);

create policy campaign_members_update_owner
on public.campaign_members
for update
to authenticated
using (
    (select private.is_campaign_owner(campaign_id))
    and role <> 'owner'
)
with check (
    (select private.is_campaign_owner(campaign_id))
    and role in ('player', 'gm')
);

create policy campaign_members_delete_owner
on public.campaign_members
for delete
to authenticated
using (
    (select private.is_campaign_owner(campaign_id))
    and role <> 'owner'
);

create policy characters_select_member
on public.characters
for select
to authenticated
using ((select private.is_campaign_member(campaign_id)));

create policy characters_insert_self
on public.characters
for insert
to authenticated
with check (
    user_id = (select auth.uid())
    and (select private.is_campaign_member(campaign_id))
);

create policy characters_update_controller
on public.characters
for update
to authenticated
using ((select private.can_manage_character(id)))
with check (
    user_id = (select auth.uid())
    or (select private.can_manage_campaign(campaign_id))
);

create policy characters_delete_owner
on public.characters
for delete
to authenticated
using ((select private.is_campaign_owner(campaign_id)));

create policy scenes_select_member
on public.scenes
for select
to authenticated
using ((select private.is_campaign_member(campaign_id)));

create policy scenes_insert_manager
on public.scenes
for insert
to authenticated
with check ((select private.can_manage_campaign(campaign_id)));

create policy scenes_update_manager
on public.scenes
for update
to authenticated
using ((select private.can_manage_campaign(campaign_id)))
with check ((select private.can_manage_campaign(campaign_id)));

create policy scenes_delete_manager
on public.scenes
for delete
to authenticated
using ((select private.can_manage_campaign(campaign_id)));

create policy entities_select_member
on public.entities
for select
to authenticated
using ((select private.is_campaign_member(campaign_id)));

create policy entities_insert_manager
on public.entities
for insert
to authenticated
with check ((select private.can_manage_campaign(campaign_id)));

create policy entities_update_manager
on public.entities
for update
to authenticated
using ((select private.can_manage_campaign(campaign_id)))
with check ((select private.can_manage_campaign(campaign_id)));

create policy entities_delete_manager
on public.entities
for delete
to authenticated
using ((select private.can_manage_campaign(campaign_id)));

create policy inventory_items_select_member
on public.inventory_items
for select
to authenticated
using ((select private.can_access_character(character_id)));

create policy inventory_items_insert_controller
on public.inventory_items
for insert
to authenticated
with check ((select private.can_manage_character(character_id)));

create policy inventory_items_update_controller
on public.inventory_items
for update
to authenticated
using ((select private.can_manage_character(character_id)))
with check ((select private.can_manage_character(character_id)));

create policy inventory_items_delete_controller
on public.inventory_items
for delete
to authenticated
using ((select private.can_manage_character(character_id)));

create policy pending_checks_select_member
on public.pending_checks
for select
to authenticated
using ((select private.is_campaign_member(campaign_id)));

create policy pending_checks_insert_controller
on public.pending_checks
for insert
to authenticated
with check (
    (select private.is_campaign_member(campaign_id))
    and (select private.can_manage_character(character_id))
);

create policy pending_checks_update_controller
on public.pending_checks
for update
to authenticated
using ((select private.can_manage_character(character_id)))
with check (
    (select private.is_campaign_member(campaign_id))
    and (select private.can_manage_character(character_id))
);

create policy pending_checks_delete_controller
on public.pending_checks
for delete
to authenticated
using ((select private.can_manage_character(character_id)));

create policy game_events_select_member
on public.game_events
for select
to authenticated
using ((select private.is_campaign_member(campaign_id)));

create policy game_events_insert_controller
on public.game_events
for insert
to authenticated
with check (
    (select private.is_campaign_member(campaign_id))
    and (
        (character_id is not null and (select private.can_manage_character(character_id)))
        or (character_id is null and (select private.can_manage_campaign(campaign_id)))
    )
);
