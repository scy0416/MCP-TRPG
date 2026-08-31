insert into private.mcp_auth_config (resource_uri)
values ('http://127.0.0.1:8000/mcp')
on conflict (singleton) do update
set resource_uri = excluded.resource_uri;
