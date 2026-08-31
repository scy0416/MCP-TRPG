create or replace function public.create_check(
    p_campaign_id uuid,
    p_character_id uuid,
    p_check_type text,
    p_dice_spec jsonb,
    p_difficulty smallint,
    p_context text
)
returns public.pending_checks
language plpgsql
security definer
set search_path = ''
as $$
declare
    character_modifier smallint;
    created_check public.pending_checks;
begin
    if (select auth.uid()) is null then
        raise exception 'authenticated user is required';
    end if;

    select case p_check_type
        when 'str' then character_record.str
        when 'dex' then character_record.dex
        when 'int' then character_record.int
        when 'cha' then character_record.cha
        else null
    end
    into character_modifier
    from public.characters character_record
    where character_record.id = p_character_id
      and character_record.campaign_id = p_campaign_id
      and (select private.can_manage_character(character_record.id));

    if character_modifier is null then
        raise exception 'character is not available to this user';
    end if;

    insert into public.pending_checks (
        campaign_id, character_id, check_type, dice_spec, modifier, difficulty, context
    )
    values (
        p_campaign_id,
        p_character_id,
        p_check_type,
        p_dice_spec,
        character_modifier,
        p_difficulty,
        p_context
    )
    returning * into created_check;

    insert into public.game_events (campaign_id, character_id, event_type, payload)
    values (
        created_check.campaign_id,
        created_check.character_id,
        'ability_check_created',
        jsonb_build_object(
            'check_id', created_check.id,
            'check_type', created_check.check_type,
            'dice_spec', created_check.dice_spec,
            'modifier', created_check.modifier,
            'difficulty', created_check.difficulty,
            'context', created_check.context
        )
    );

    return created_check;
end;
$$;

revoke all on function public.create_check(uuid, uuid, text, jsonb, smallint, text)
from public, anon;
grant execute on function public.create_check(uuid, uuid, text, jsonb, smallint, text)
to authenticated;
