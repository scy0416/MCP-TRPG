begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(34);

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
        '11000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000000',
        'authenticated',
        'authenticated',
        'owner@rls.test',
        '',
        '{"display_name":"RLS Owner"}',
        now(),
        now()
    ),
    (
        '11000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000000',
        'authenticated',
        'authenticated',
        'player@rls.test',
        '',
        '{"display_name":"RLS Player"}',
        now(),
        now()
    ),
    (
        '11000000-0000-0000-0000-000000000003',
        '00000000-0000-0000-0000-000000000000',
        'authenticated',
        'authenticated',
        'outsider@rls.test',
        '',
        '{"display_name":"RLS Outsider"}',
        now(),
        now()
    );

insert into public.campaigns (id, owner_id, title)
values
    (
        '21000000-0000-0000-0000-000000000001',
        '11000000-0000-0000-0000-000000000001',
        'Shared Campaign'
    ),
    (
        '21000000-0000-0000-0000-000000000002',
        '11000000-0000-0000-0000-000000000003',
        'Private Campaign'
    );

insert into public.campaign_members (campaign_id, user_id, role)
values (
    '21000000-0000-0000-0000-000000000001',
    '11000000-0000-0000-0000-000000000002',
    'player'
);

insert into public.characters (
    id, campaign_id, user_id, name, hp, max_hp, str, dex, int, cha
)
values
    (
        '31000000-0000-0000-0000-000000000001',
        '21000000-0000-0000-0000-000000000001',
        '11000000-0000-0000-0000-000000000001',
        'Owner Character', 13, 13, 3, 2, 1, 0
    ),
    (
        '31000000-0000-0000-0000-000000000002',
        '21000000-0000-0000-0000-000000000001',
        '11000000-0000-0000-0000-000000000002',
        'Player Character', 12, 12, 2, 3, 1, 0
    ),
    (
        '31000000-0000-0000-0000-000000000003',
        '21000000-0000-0000-0000-000000000002',
        '11000000-0000-0000-0000-000000000003',
        'Outsider Character', 11, 11, 1, 3, 2, 0
    );

insert into public.scenes (id, campaign_id, name, description)
values
    (
        '41000000-0000-0000-0000-000000000001',
        '21000000-0000-0000-0000-000000000001',
        'Shared Scene',
        'Visible to members of the shared campaign.'
    ),
    (
        '41000000-0000-0000-0000-000000000002',
        '21000000-0000-0000-0000-000000000002',
        'Private Scene',
        'Visible only to members of the private campaign.'
    );

insert into public.inventory_items (id, character_id, item_type, name, quantity)
values
    (
        '51000000-0000-0000-0000-000000000001',
        '31000000-0000-0000-0000-000000000002',
        'consumable',
        'Potion',
        1
    ),
    (
        '51000000-0000-0000-0000-000000000002',
        '31000000-0000-0000-0000-000000000003',
        'consumable',
        'Private Potion',
        1
    );

insert into public.game_events (id, campaign_id, character_id, event_type, payload)
values (
    '61000000-0000-0000-0000-000000000001',
    '21000000-0000-0000-0000-000000000001',
    '31000000-0000-0000-0000-000000000002',
    'character_created',
    '{"source":"fixture"}'
);

select results_eq(
    $$
        select relname
        from pg_class
        join pg_namespace on pg_namespace.oid = pg_class.relnamespace
        where pg_namespace.nspname = 'public'
          and relname in (
              'profiles', 'campaigns', 'campaign_members', 'characters',
              'scenes', 'entities', 'inventory_items', 'pending_checks',
              'game_events'
          )
          and relrowsecurity
        order by relname
    $$,
    array[
        'campaign_members'::name,
        'campaigns'::name,
        'characters'::name,
        'entities'::name,
        'game_events'::name,
        'inventory_items'::name,
        'pending_checks'::name,
        'profiles'::name,
        'scenes'::name
    ],
    'RLS is enabled on every public application table'
);

select ok(
    not has_table_privilege('anon', 'public.campaigns', 'SELECT'),
    'anon has no campaign read grant'
);

select ok(
    not has_table_privilege('anon', 'public.game_events', 'INSERT'),
    'anon has no event write grant'
);

select ok(
    not has_function_privilege(
        'anon',
        'private.is_campaign_member(uuid)',
        'EXECUTE'
    ),
    'anon cannot execute private authorization helpers'
);

set local role authenticated;
select set_config(
    'request.jwt.claim.sub',
    '11000000-0000-0000-0000-000000000002',
    true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

select results_eq(
    'select title from public.campaigns order by title',
    array['Shared Campaign'::text],
    'player sees only campaigns they belong to'
);

select results_eq(
    'select name from public.characters order by name',
    array['Owner Character'::text, 'Player Character'::text],
    'player sees all characters in their campaign only'
);

select results_eq(
    'select display_name from public.profiles order by display_name',
    array['RLS Owner'::text, 'RLS Player'::text],
    'player sees only profiles sharing a campaign'
);

select results_eq(
    $$
        update public.profiles
        set display_name = 'Forged Name'
        where id = '11000000-0000-0000-0000-000000000001'
        returning display_name
    $$,
    array[]::text[],
    'player cannot update another profile by UUID'
);

select lives_ok(
    $$
        update public.profiles
        set display_name = 'Updated Player'
        where id = '11000000-0000-0000-0000-000000000002'
    $$,
    'player can update their own profile'
);

select throws_like(
    $$
        insert into public.characters (
            campaign_id, user_id, name, hp, max_hp, str, dex, int, cha
        )
        values (
            '21000000-0000-0000-0000-000000000001',
            '11000000-0000-0000-0000-000000000003',
            'Forged Character', 13, 13, 3, 2, 1, 0
        )
    $$,
    '%row-level security policy%',
    'player cannot create a character for another user'
);

select results_eq(
    $$
        update public.characters
        set hp = 11
        where id = '31000000-0000-0000-0000-000000000001'
        returning hp
    $$,
    array[]::smallint[],
    'player cannot update another member character by UUID'
);

select results_eq(
    $$
        update public.characters
        set hp = 11
        where id = '31000000-0000-0000-0000-000000000002'
        returning hp
    $$,
    array[11::smallint],
    'player can update their own character'
);

select throws_like(
    $$
        update public.characters
        set campaign_id = '21000000-0000-0000-0000-000000000002'
        where id = '31000000-0000-0000-0000-000000000002'
    $$,
    '%permission denied%',
    'player cannot re-parent a character by changing campaign UUID'
);

select throws_like(
    $$
        insert into public.scenes (campaign_id, name, description)
        values (
            '21000000-0000-0000-0000-000000000001',
            'Forged Scene',
            'A player must not create campaign-owned state.'
        )
    $$,
    '%row-level security policy%',
    'player cannot create manager-owned scene state'
);

select results_eq(
    $$
        update public.inventory_items
        set quantity = 2
        where id = '51000000-0000-0000-0000-000000000001'
        returning quantity
    $$,
    array[2],
    'player can update their own inventory'
);

select results_eq(
    $$
        update public.inventory_items
        set quantity = 2
        where id = '51000000-0000-0000-0000-000000000002'
        returning quantity
    $$,
    array[]::integer[],
    'player cannot update an outsider inventory by UUID'
);

select throws_like(
    $$
        update public.inventory_items
        set character_id = '31000000-0000-0000-0000-000000000001'
        where id = '51000000-0000-0000-0000-000000000001'
    $$,
    '%permission denied%',
    'player cannot transfer inventory by changing character UUID'
);

select lives_ok(
    $$
        insert into public.pending_checks (
            id, campaign_id, character_id, check_type, dice_spec,
            modifier, difficulty, context
        )
        values (
            '71000000-0000-0000-0000-000000000001',
            '21000000-0000-0000-0000-000000000001',
            '31000000-0000-0000-0000-000000000002',
            'dex', '{"count":1,"sides":20}', 3, 12, 'Dodge the trap'
        )
    $$,
    'player can create a check for their own character'
);

select throws_like(
    $$
        insert into public.pending_checks (
            campaign_id, character_id, check_type, dice_spec,
            modifier, difficulty, context
        )
        values (
            '21000000-0000-0000-0000-000000000002',
            '31000000-0000-0000-0000-000000000003',
            'dex', '{"count":1,"sides":20}', 3, 12, 'Forged check'
        )
    $$,
    '%row-level security policy%',
    'player cannot create a check in an outsider campaign'
);

select lives_ok(
    $$
        insert into public.game_events (
            campaign_id, character_id, event_type, payload
        )
        values (
            '21000000-0000-0000-0000-000000000001',
            '31000000-0000-0000-0000-000000000002',
            'ability_check_created',
            '{"check_id":"71000000-0000-0000-0000-000000000001"}'
        )
    $$,
    'player can append an event for their own character'
);

select throws_like(
    $$
        insert into public.game_events (
            campaign_id, character_id, event_type, payload
        )
        values (
            '21000000-0000-0000-0000-000000000002',
            '31000000-0000-0000-0000-000000000003',
            'character_created',
            '{"source":"forged"}'
        )
    $$,
    '%row-level security policy%',
    'player cannot append an event to an outsider campaign'
);

select throws_like(
    $$
        update public.game_events
        set payload = '{"tampered":true}'
        where id = '61000000-0000-0000-0000-000000000001'
    $$,
    '%permission denied%',
    'authenticated users cannot update append-only events'
);

select throws_like(
    $$
        delete from public.game_events
        where id = '61000000-0000-0000-0000-000000000001'
    $$,
    '%permission denied%',
    'authenticated users cannot delete append-only events'
);

reset role;
set local role authenticated;
select set_config(
    'request.jwt.claim.sub',
    '11000000-0000-0000-0000-000000000001',
    true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

select lives_ok(
    $$
        insert into public.scenes (campaign_id, name, description)
        values (
            '21000000-0000-0000-0000-000000000001',
            'Owner Scene',
            'Campaign managers may create shared state.'
        )
    $$,
    'campaign owner can create scene state'
);

select lives_ok(
    $$
        update public.characters
        set hp = 10
        where id = '31000000-0000-0000-0000-000000000002'
    $$,
    'campaign owner can manage a member character'
);

select results_eq(
    $$
        update public.campaign_members
        set role = 'gm'
        where campaign_id = '21000000-0000-0000-0000-000000000001'
          and user_id = '11000000-0000-0000-0000-000000000001'
        returning role
    $$,
    array[]::text[],
    'campaign owner cannot demote the immutable owner membership'
);

select lives_ok(
    $$
        update public.campaign_members
        set role = 'gm'
        where campaign_id = '21000000-0000-0000-0000-000000000001'
          and user_id = '11000000-0000-0000-0000-000000000002'
    $$,
    'campaign owner can promote a non-owner member'
);

select lives_ok(
    $$
        insert into public.game_events (campaign_id, event_type, payload)
        values (
            '21000000-0000-0000-0000-000000000001',
            'scene_changed',
            '{"source":"owner"}'
        )
    $$,
    'campaign manager can append a campaign-level event'
);

reset role;
set local role authenticated;
select set_config(
    'request.jwt.claim.sub',
    '11000000-0000-0000-0000-000000000003',
    true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

select results_eq(
    'select title from public.campaigns order by title',
    array['Private Campaign'::text],
    'outsider cannot discover the shared campaign by UUID'
);

select results_eq(
    $$
        select name
        from public.scenes
        where id = '41000000-0000-0000-0000-000000000001'
    $$,
    array[]::text[],
    'outsider cannot read a shared campaign scene by UUID'
);

select results_eq(
    $$
        delete from public.characters
        where id = '31000000-0000-0000-0000-000000000002'
        returning name
    $$,
    array[]::text[],
    'outsider cannot delete a shared campaign character by UUID'
);

select throws_like(
    $$
        insert into public.campaign_members (campaign_id, user_id, role)
        values (
            '21000000-0000-0000-0000-000000000001',
            '11000000-0000-0000-0000-000000000003',
            'player'
        )
    $$,
    '%row-level security policy%',
    'outsider cannot add themselves to a campaign'
);

reset role;
set local role service_role;

select is(
    (select count(*) from public.campaigns),
    2::bigint,
    'service role can read all campaigns for trusted server operations'
);

select lives_ok(
    $$
        update public.game_events
        set payload = payload || '{"trusted":true}'::jsonb
        where id = '61000000-0000-0000-0000-000000000001'
    $$,
    'service role retains trusted maintenance access to events'
);

reset role;

select * from finish();
rollback;
