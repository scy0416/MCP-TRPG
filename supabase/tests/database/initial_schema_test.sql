begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(25);

select has_table('public', 'profiles', 'profiles table exists');
select has_table('public', 'campaigns', 'campaigns table exists');
select has_table('public', 'campaign_members', 'campaign_members table exists');
select has_table('public', 'characters', 'characters table exists');
select has_table('public', 'scenes', 'scenes table exists');
select has_table('public', 'entities', 'entities table exists');
select has_table('public', 'inventory_items', 'inventory_items table exists');
select has_table('public', 'pending_checks', 'pending_checks table exists');
select has_table('public', 'game_events', 'game_events table exists');

insert into auth.users (
    id,
    instance_id,
    aud,
    role,
    email,
    encrypted_password,
    raw_user_meta_data,
    created_at,
    updated_at
)
values
    (
        '10000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000000',
        'authenticated',
        'authenticated',
        'owner@example.test',
        '',
        '{"display_name":"Owner"}',
        now(),
        now()
    ),
    (
        '10000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000000',
        'authenticated',
        'authenticated',
        'other@example.test',
        '',
        '{"display_name":"Other"}',
        now(),
        now()
    );

select is(
    (select count(*) from public.profiles),
    2::bigint,
    'auth user inserts create profiles'
);

insert into public.campaigns (id, owner_id, title)
values
    (
        '20000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        'First Campaign'
    ),
    (
        '20000000-0000-0000-0000-000000000002',
        '10000000-0000-0000-0000-000000000002',
        'Other Campaign'
    );

select results_eq(
    $$
        select role
        from public.campaign_members
        where campaign_id = '20000000-0000-0000-0000-000000000001'
          and user_id = '10000000-0000-0000-0000-000000000001'
    $$,
    array['owner'::text],
    'campaign creation registers its owner as a member'
);

select lives_ok(
    $$
        insert into public.characters (
            id, campaign_id, user_id, name, hp, max_hp, str, dex, int, cha
        )
        values (
            '30000000-0000-0000-0000-000000000001',
            '20000000-0000-0000-0000-000000000001',
            '10000000-0000-0000-0000-000000000001',
            'Arin', 13, 13, 3, 2, 1, 0
        )
    $$,
    'valid MVP character can be created'
);

select throws_like(
    $$
        insert into public.characters (
            campaign_id, user_id, name, hp, max_hp, str, dex, int, cha
        )
        values (
            '20000000-0000-0000-0000-000000000002',
            '10000000-0000-0000-0000-000000000001',
            'Invalid Stats', 13, 13, 3, 3, 0, 0
        )
    $$,
    '%characters_stats_unique%',
    'duplicate ability modifiers are rejected'
);

select throws_like(
    $$
        update public.characters
        set hp = 14
        where id = '30000000-0000-0000-0000-000000000001'
    $$,
    '%characters_hp_range%',
    'HP above max HP is rejected'
);

insert into public.scenes (id, campaign_id, name, description)
values
    (
        '40000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000001',
        'Old Gate',
        'A locked iron gate blocks the road.'
    ),
    (
        '40000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000002',
        'Other Scene',
        'This scene belongs to a different campaign.'
    );

select lives_ok(
    $$
        update public.campaigns
        set current_scene_id = '40000000-0000-0000-0000-000000000001'
        where id = '20000000-0000-0000-0000-000000000001'
    $$,
    'campaign can select one of its own scenes'
);

select throws_like(
    $$
        update public.campaigns
        set current_scene_id = '40000000-0000-0000-0000-000000000002'
        where id = '20000000-0000-0000-0000-000000000001'
    $$,
    '%campaigns_current_scene_belongs_to_campaign%',
    'campaign cannot select another campaign scene'
);

select throws_like(
    $$
        insert into public.entities (
            campaign_id, scene_id, entity_type, name, description
        )
        values (
            '20000000-0000-0000-0000-000000000001',
            '40000000-0000-0000-0000-000000000002',
            'npc', 'Wrong NPC', 'The relation is invalid.'
        )
    $$,
    '%entities_scene_belongs_to_campaign%',
    'entity scene must belong to its campaign'
);

select throws_like(
    $$
        insert into public.inventory_items (character_id, item_type, name, quantity)
        values (
            '30000000-0000-0000-0000-000000000001',
            'consumable', 'Potion', 0
        )
    $$,
    '%inventory_items_quantity_positive%',
    'zero quantity items are not stored'
);

select lives_ok(
    $$
        insert into public.pending_checks (
            id,
            campaign_id,
            character_id,
            check_type,
            dice_spec,
            modifier,
            difficulty,
            context
        )
        values (
            '50000000-0000-0000-0000-000000000001',
            '20000000-0000-0000-0000-000000000001',
            '30000000-0000-0000-0000-000000000001',
            'str',
            '{"count":1,"sides":20}',
            3,
            15,
            'Break the locked iron gate'
        )
    $$,
    'valid ability check can be created'
);

select throws_like(
    $$
        insert into public.pending_checks (
            campaign_id,
            character_id,
            check_type,
            dice_spec,
            modifier,
            difficulty,
            context
        )
        values (
            '20000000-0000-0000-0000-000000000001',
            '30000000-0000-0000-0000-000000000001',
            'dex',
            '{"count":1,"sides":20}',
            2,
            10,
            'Create a second pending check'
        )
    $$,
    '%pending_checks_one_open_per_campaign_idx%',
    'campaign cannot have two pending checks'
);

select throws_like(
    $$
        update public.pending_checks
        set dice_spec = '{"count":"one","sides":20}'
        where id = '50000000-0000-0000-0000-000000000001'
    $$,
    '%pending_checks_dice_valid%',
    'malformed dice specification is rejected'
);

select throws_like(
    $$
        update public.pending_checks
        set status = 'resolved'
        where id = '50000000-0000-0000-0000-000000000001'
    $$,
    '%pending_checks_resolution_consistent%',
    'resolved checks require a resolution timestamp'
);

select lives_ok(
    $$
        update public.pending_checks
        set status = 'resolved', resolved_at = now()
        where id = '50000000-0000-0000-0000-000000000001'
    $$,
    'pending check can be resolved consistently'
);

select throws_like(
    $$
        insert into public.game_events (campaign_id, event_type, payload)
        values (
            '20000000-0000-0000-0000-000000000001',
            'campaign_created',
            '[]'
        )
    $$,
    '%game_events_payload_object%',
    'event payload must be an object'
);

update public.campaigns
set updated_at = '2000-01-01 00:00:00+00'
where id = '20000000-0000-0000-0000-000000000001';

update public.campaigns
set title = 'Renamed Campaign'
where id = '20000000-0000-0000-0000-000000000001';

select cmp_ok(
    (
        select updated_at
        from public.campaigns
        where id = '20000000-0000-0000-0000-000000000001'
    ),
    '>',
    '2000-01-01 00:00:00+00'::timestamptz,
    'updates refresh updated_at'
);

select * from finish();
rollback;
