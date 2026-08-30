create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create or replace function public.is_valid_dice_spec(value jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
    dice_count integer;
    dice_sides integer;
begin
    if jsonb_typeof(value) <> 'object'
        or not value ? 'count'
        or not value ? 'sides'
        or value - array['count', 'sides'] <> '{}'::jsonb
    then
        return false;
    end if;

    dice_count := (value ->> 'count')::integer;
    dice_sides := (value ->> 'sides')::integer;

    return dice_count between 1 and 20 and dice_sides between 2 and 100;
exception
    when invalid_text_representation or numeric_value_out_of_range then
        return false;
end;
$$;

create table public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    display_name text not null,
    created_at timestamptz not null default now(),

    constraint profiles_display_name_length
        check (char_length(btrim(display_name)) between 1 and 80)
);

create or replace function public.create_profile_for_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.profiles (id, display_name)
    values (
        new.id,
        coalesce(nullif(btrim(new.raw_user_meta_data ->> 'display_name'), ''), 'Player')
    );
    return new;
end;
$$;

create trigger create_profile_after_user_insert
after insert on auth.users
for each row execute function public.create_profile_for_new_user();

create table public.campaigns (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users (id) on delete cascade,
    title text not null,
    status text not null default 'active',
    current_scene_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint campaigns_title_length
        check (char_length(btrim(title)) between 1 and 120),
    constraint campaigns_status_allowed
        check (status in ('active', 'completed', 'archived'))
);

create table public.campaign_members (
    campaign_id uuid not null references public.campaigns (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    role text not null default 'player',
    created_at timestamptz not null default now(),

    primary key (campaign_id, user_id),
    constraint campaign_members_role_allowed
        check (role in ('owner', 'player', 'gm'))
);

create unique index campaign_members_one_owner_idx
on public.campaign_members (campaign_id)
where role = 'owner';

create index campaign_members_user_idx
on public.campaign_members (user_id, campaign_id);

create or replace function public.add_campaign_owner_membership()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.campaign_members (campaign_id, user_id, role)
    values (new.id, new.owner_id, 'owner');
    return new;
end;
$$;

create trigger add_campaign_owner_after_insert
after insert on public.campaigns
for each row execute function public.add_campaign_owner_membership();

create or replace function public.prevent_campaign_owner_change()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if new.owner_id <> old.owner_id then
        raise exception 'campaign ownership transfer is not supported';
    end if;
    return new;
end;
$$;

create trigger prevent_campaign_owner_change_before_update
before update of owner_id on public.campaigns
for each row execute function public.prevent_campaign_owner_change();

create table public.characters (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns (id) on delete cascade,
    user_id uuid not null references auth.users (id) on delete cascade,
    name text not null,
    hp smallint not null,
    max_hp smallint not null,
    str smallint not null,
    dex smallint not null,
    int smallint not null,
    cha smallint not null,
    status jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint characters_id_campaign_unique unique (id, campaign_id),
    constraint characters_one_per_user_per_campaign unique (campaign_id, user_id),
    constraint characters_name_length
        check (char_length(btrim(name)) between 1 and 80),
    constraint characters_stats_range
        check (
            str between 0 and 3
            and dex between 0 and 3
            and int between 0 and 3
            and cha between 0 and 3
        ),
    constraint characters_stats_unique
        check (
            str <> dex and str <> int and str <> cha
            and dex <> int and dex <> cha and int <> cha
        ),
    constraint characters_max_hp_matches_strength
        check (max_hp = 10 + str),
    constraint characters_hp_range
        check (hp between 0 and max_hp),
    constraint characters_status_object
        check (jsonb_typeof(status) = 'object')
);

create index characters_user_idx
on public.characters (user_id, campaign_id);

create table public.scenes (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns (id) on delete cascade,
    name text not null,
    description text not null,
    state jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint scenes_id_campaign_unique unique (id, campaign_id),
    constraint scenes_name_length
        check (char_length(btrim(name)) between 1 and 120),
    constraint scenes_description_length
        check (char_length(btrim(description)) between 1 and 5000),
    constraint scenes_state_object
        check (jsonb_typeof(state) = 'object')
);

create index scenes_campaign_idx
on public.scenes (campaign_id, created_at);

alter table public.campaigns
add constraint campaigns_current_scene_belongs_to_campaign
foreign key (current_scene_id, id)
references public.scenes (id, campaign_id)
on delete set null (current_scene_id);

create table public.entities (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns (id) on delete cascade,
    scene_id uuid not null,
    entity_type text not null,
    name text not null,
    description text not null,
    state jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint entities_scene_belongs_to_campaign
        foreign key (scene_id, campaign_id)
        references public.scenes (id, campaign_id)
        on delete cascade,
    constraint entities_type_allowed
        check (entity_type in ('npc', 'enemy', 'object', 'door', 'chest')),
    constraint entities_name_length
        check (char_length(btrim(name)) between 1 and 120),
    constraint entities_description_length
        check (char_length(btrim(description)) between 1 and 5000),
    constraint entities_state_object
        check (jsonb_typeof(state) = 'object')
);

create index entities_scene_idx
on public.entities (campaign_id, scene_id, entity_type);

create table public.inventory_items (
    id uuid primary key default gen_random_uuid(),
    character_id uuid not null references public.characters (id) on delete cascade,
    item_type text not null,
    name text not null,
    quantity integer not null default 1,
    state jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint inventory_items_stack_unique unique (character_id, item_type, name),
    constraint inventory_items_type_length
        check (char_length(btrim(item_type)) between 1 and 80),
    constraint inventory_items_name_length
        check (char_length(btrim(name)) between 1 and 120),
    constraint inventory_items_quantity_positive
        check (quantity > 0),
    constraint inventory_items_state_object
        check (jsonb_typeof(state) = 'object')
);

create index inventory_items_character_idx
on public.inventory_items (character_id, created_at);

create table public.pending_checks (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns (id) on delete cascade,
    character_id uuid not null,
    check_type text not null,
    dice_spec jsonb not null,
    modifier smallint not null,
    difficulty smallint not null,
    context text not null,
    status text not null default 'pending',
    created_at timestamptz not null default now(),
    resolved_at timestamptz,

    constraint pending_checks_character_belongs_to_campaign
        foreign key (character_id, campaign_id)
        references public.characters (id, campaign_id)
        on delete cascade,
    constraint pending_checks_type_allowed
        check (check_type in ('str', 'dex', 'int', 'cha')),
    constraint pending_checks_dice_valid
        check (public.is_valid_dice_spec(dice_spec)),
    constraint pending_checks_modifier_range
        check (modifier between -10 and 10),
    constraint pending_checks_difficulty_range
        check (difficulty between 5 and 25),
    constraint pending_checks_context_length
        check (char_length(btrim(context)) between 1 and 1000),
    constraint pending_checks_status_allowed
        check (status in ('pending', 'resolved', 'expired', 'cancelled')),
    constraint pending_checks_resolution_consistent
        check ((status = 'resolved') = (resolved_at is not null))
);

create unique index pending_checks_one_open_per_campaign_idx
on public.pending_checks (campaign_id)
where status = 'pending';

create index pending_checks_character_status_idx
on public.pending_checks (character_id, status, created_at desc);

create table public.game_events (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns (id) on delete cascade,
    character_id uuid,
    event_type text not null,
    payload jsonb not null,
    created_at timestamptz not null default now(),

    constraint game_events_character_belongs_to_campaign
        foreign key (character_id, campaign_id)
        references public.characters (id, campaign_id)
        on delete cascade,
    constraint game_events_type_allowed
        check (
            event_type in (
                'campaign_created',
                'character_created',
                'ability_check_created',
                'ability_check_resolved',
                'interaction_completed',
                'item_acquired',
                'item_used',
                'hp_changed',
                'scene_changed'
            )
        ),
    constraint game_events_payload_object
        check (jsonb_typeof(payload) = 'object')
);

create index game_events_campaign_created_idx
on public.game_events (campaign_id, created_at desc, id);

create index game_events_character_created_idx
on public.game_events (character_id, created_at desc)
where character_id is not null;

create trigger campaigns_set_updated_at
before update on public.campaigns
for each row execute function public.set_updated_at();

create trigger characters_set_updated_at
before update on public.characters
for each row execute function public.set_updated_at();

create trigger scenes_set_updated_at
before update on public.scenes
for each row execute function public.set_updated_at();

create trigger entities_set_updated_at
before update on public.entities
for each row execute function public.set_updated_at();

create trigger inventory_items_set_updated_at
before update on public.inventory_items
for each row execute function public.set_updated_at();
