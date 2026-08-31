begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(8);

select has_function(
    'public',
    'create_check',
    array['uuid', 'uuid', 'text', 'jsonb', 'smallint', 'text'],
    'create_check RPC exists'
);

select ok(
    has_function_privilege(
        'authenticated',
        'public.create_check(uuid, uuid, text, jsonb, smallint, text)',
        'EXECUTE'
    ),
    'authenticated users can execute create_check RPC'
);

select ok(
    not has_function_privilege(
        'anon',
        'public.create_check(uuid, uuid, text, jsonb, smallint, text)',
        'EXECUTE'
    ),
    'anonymous users cannot execute create_check RPC'
);

insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, raw_user_meta_data, created_at, updated_at
)
values (
    '13000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'check@example.test', '', '{}', now(), now()
);

set local role authenticated;
select set_config('request.jwt.claim.sub', '13000000-0000-0000-0000-000000000001', true);
select set_config('request.jwt.claim.role', 'authenticated', true);

select is(
    (public.create_campaign('Check Campaign')).title,
    'Check Campaign'::text,
    'check fixture campaign is created'
);

select is(
    (
        public.create_character(
            (select id from public.campaigns where title = 'Check Campaign'),
            'Check Arin', 3::smallint, 2::smallint, 1::smallint, 0::smallint
        )
    ).name,
    'Check Arin'::text,
    'check fixture character is created'
);

select is(
    (
        public.create_check(
            (select id from public.campaigns where title = 'Check Campaign'),
            (select id from public.characters where name = 'Check Arin'),
            'str', '{"count":1,"sides":20}'::jsonb, 15::smallint, 'Break the locked door'
        )
    ).modifier,
    3::smallint,
    'create_check stores the modifier from the character'
);

select is(
    (select count(*) from public.pending_checks where status = 'pending'),
    1::bigint,
    'create_check creates one pending check'
);

select is(
    (select count(*) from public.game_events where event_type = 'ability_check_created'),
    1::bigint,
    'create_check records its creation event'
);

select * from finish();
rollback;
