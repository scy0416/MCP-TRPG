create table private.mcp_auth_config (
    singleton boolean primary key default true,
    resource_uri text not null,

    constraint mcp_auth_config_single_row check (singleton),
    constraint mcp_auth_config_resource_uri check (
        resource_uri ~ '^https://[^?#]+/mcp$'
        or resource_uri ~ '^http://(127[.]0[.]0[.]1|localhost)(:[0-9]+)?/mcp$'
    )
);

revoke all on table private.mcp_auth_config from public, anon, authenticated;
grant usage on schema private to supabase_auth_admin;
grant select on table private.mcp_auth_config to supabase_auth_admin;

create or replace function private.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
set search_path = ''
as $$
declare
    claims jsonb;
    resource_uri text;
begin
    claims := event -> 'claims';

    if claims ->> 'client_id' is null then
        return jsonb_build_object('claims', claims);
    end if;

    select config.resource_uri
    into resource_uri
    from private.mcp_auth_config config
    where config.singleton;

    if resource_uri is null then
        raise exception 'MCP resource URI is not configured';
    end if;

    claims := jsonb_set(claims, '{aud}', to_jsonb(resource_uri));
    return jsonb_build_object('claims', claims);
end;
$$;

grant execute on function private.custom_access_token_hook(jsonb) to supabase_auth_admin;
revoke execute on function private.custom_access_token_hook(jsonb)
from public, anon, authenticated;
