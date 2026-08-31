create or replace function public.create_campaign(p_title text)
returns public.campaigns
language plpgsql
security definer
set search_path = ''
as $$
declare
    created_campaign public.campaigns;
begin
    if (select auth.uid()) is null then
        raise exception 'authenticated user is required';
    end if;

    insert into public.campaigns (owner_id, title, status)
    values ((select auth.uid()), p_title, 'active')
    returning * into created_campaign;

    insert into public.game_events (campaign_id, event_type, payload)
    values (
        created_campaign.id,
        'campaign_created',
        jsonb_build_object('title', created_campaign.title, 'status', created_campaign.status)
    );

    return created_campaign;
end;
$$;

create or replace function public.create_character(
    p_campaign_id uuid,
    p_name text,
    p_str smallint,
    p_dex smallint,
    p_int smallint,
    p_cha smallint
)
returns public.characters
language plpgsql
security definer
set search_path = ''
as $$
declare
    created_character public.characters;
begin
    if (select auth.uid()) is null then
        raise exception 'authenticated user is required';
    end if;

    if not exists (
        select 1
        from public.campaign_members
        where campaign_id = p_campaign_id
          and user_id = (select auth.uid())
    ) then
        raise exception 'campaign membership is required';
    end if;

    insert into public.characters (
        campaign_id, user_id, name, hp, max_hp, str, dex, int, cha
    )
    values (
        p_campaign_id,
        (select auth.uid()),
        p_name,
        10 + p_str,
        10 + p_str,
        p_str,
        p_dex,
        p_int,
        p_cha
    )
    returning * into created_character;

    insert into public.game_events (campaign_id, character_id, event_type, payload)
    values (
        created_character.campaign_id,
        created_character.id,
        'character_created',
        jsonb_build_object(
            'name', created_character.name,
            'stats', jsonb_build_object(
                'str', created_character.str,
                'dex', created_character.dex,
                'int', created_character.int,
                'cha', created_character.cha
            )
        )
    );

    return created_character;
end;
$$;

revoke all on function public.create_campaign(text) from public, anon;
revoke all on function public.create_character(uuid, text, smallint, smallint, smallint, smallint)
from public, anon;
grant execute on function public.create_campaign(text) to authenticated;
grant execute on function public.create_character(uuid, text, smallint, smallint, smallint, smallint)
to authenticated;
