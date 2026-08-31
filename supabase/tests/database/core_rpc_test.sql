begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(8);

select has_function(
    'public',
    'create_campaign',
    array['text'],
    'campaign creation RPC exists'
);

select has_function(
    'public',
    'create_character',
    array['uuid', 'text', 'smallint', 'smallint', 'smallint', 'smallint'],
    'character creation RPC exists'
);

select ok(
    has_function_privilege('authenticated', 'public.create_campaign(text)', 'EXECUTE'),
    'authenticated users can execute campaign creation RPC'
);

select ok(
    not has_function_privilege('anon', 'public.create_campaign(text)', 'EXECUTE'),
    'anonymous users cannot execute campaign creation RPC'
);

insert into auth.users (
    id, instance_id, aud, role, email, encrypted_password, raw_user_meta_data, created_at, updated_at
)
values (
    '12000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'rpc@example.test', '', '{}', now(), now()
);

set local role authenticated;
select set_config('request.jwt.claim.sub', '12000000-0000-0000-0000-000000000001', true);
select set_config('request.jwt.claim.role', 'authenticated', true);

select is(
    (public.create_campaign('RPC Campaign')).title,
    'RPC Campaign'::text,
    'authenticated owner can create a campaign through RPC'
);

select is(
    (select count(*) from public.game_events where event_type = 'campaign_created'),
    1::bigint,
    'campaign RPC records its creation event atomically'
);

select is(
    (
        public.create_character(
            (select id from public.campaigns where title = 'RPC Campaign'),
            'RPC Arin', 3::smallint, 2::smallint, 1::smallint, 0::smallint
        )
    ).name,
    'RPC Arin'::text,
    'campaign owner can create a character through RPC'
);

select is(
    (select count(*) from public.game_events where event_type = 'character_created'),
    1::bigint,
    'character RPC records its creation event atomically'
);

select * from finish();
rollback;
