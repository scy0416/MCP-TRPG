begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(6);

select has_function(
    'private',
    'custom_access_token_hook',
    array['jsonb'],
    'OAuth custom access token hook exists'
);

select ok(
    has_function_privilege(
        'supabase_auth_admin',
        'private.custom_access_token_hook(jsonb)',
        'EXECUTE'
    ),
    'Supabase Auth can execute the token hook'
);

select ok(
    not has_function_privilege(
        'authenticated',
        'private.custom_access_token_hook(jsonb)',
        'EXECUTE'
    ),
    'authenticated users cannot execute the token hook'
);

select is(
    private.custom_access_token_hook(
        '{"claims":{"aud":"authenticated","client_id":"oauth-client"}}'::jsonb
    ) -> 'claims' ->> 'aud',
    'http://127.0.0.1:8000/mcp',
    'OAuth access tokens are audience-bound to the local MCP resource'
);

select is(
    private.custom_access_token_hook(
        '{"claims":{"aud":"authenticated"},"authentication_method":"password"}'::jsonb
    ) -> 'claims' ->> 'aud',
    'authenticated',
    'non-OAuth Supabase sessions retain their original audience'
);

delete from private.mcp_auth_config;

select throws_like(
    $$
        select private.custom_access_token_hook(
            '{"claims":{"aud":"authenticated","client_id":"oauth-client"}}'::jsonb
        )
    $$,
    '%MCP resource URI is not configured%',
    'OAuth token issuance fails closed without a configured resource URI'
);

select * from finish();
rollback;
