begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(10);

select has_function(
    'public',
    'resolve_check',
    array['uuid', 'jsonb'],
    'resolve_check RPC exists'
);

select ok(
    has_function_privilege(
        'authenticated', 'public.resolve_check(uuid, jsonb)', 'EXECUTE'
    ),
    'authenticated users can execute resolve_check RPC'
);

select ok(
    not has_function_privilege(
        'anon', 'public.resolve_check(uuid, jsonb)', 'EXECUTE'
    ),
    'anonymous users cannot execute resolve_check RPC'
);

insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, raw_user_meta_data, created_at, updated_at
)
values (
    '14000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'resolve@example.test', '', '{}', now(), now()
);

set local role authenticated;
select set_config('request.jwt.claim.sub', '14000000-0000-0000-0000-000000000001', true);
select set_config('request.jwt.claim.role', 'authenticated', true);

select is(
    (public.create_campaign('Resolve Campaign')).title,
    'Resolve Campaign'::text,
    'resolve fixture campaign is created'
);

select is(
    (
        public.create_character(
            (select id from public.campaigns where title = 'Resolve Campaign'),
            'Resolve Arin', 3::smallint, 2::smallint, 1::smallint, 0::smallint
        )
    ).name,
    'Resolve Arin'::text,
    'resolve fixture character is created'
);

select is(
    (
        public.create_check(
            (select id from public.campaigns where title = 'Resolve Campaign'),
            (select id from public.characters where name = 'Resolve Arin'),
            'str', '{"count":1,"sides":20}'::jsonb, 15::smallint, 'Break the locked door'
        )
    ).status,
    'pending'::text,
    'resolve fixture check is pending'
);

select is(
    (
        public.resolve_check(
            (select id from public.pending_checks where context = 'Break the locked door'),
            '[16]'::jsonb
        ) ->> 'total'
    )::integer,
    19,
    'resolve_check calculates total from stored modifier'
);

select is(
    (
        public.resolve_check(
            (select id from public.pending_checks where context = 'Break the locked door'),
            '[1]'::jsonb
        ) ->> 'total'
    )::integer,
    19,
    'duplicate resolution returns the first result'
);

select is(
    (select status from public.pending_checks where context = 'Break the locked door'),
    'resolved'::text,
    'resolved check status is persisted'
);

select is(
    (select count(*) from public.game_events where event_type = 'ability_check_resolved'),
    1::bigint,
    'resolution event is recorded once'
);

select * from finish();
rollback;
