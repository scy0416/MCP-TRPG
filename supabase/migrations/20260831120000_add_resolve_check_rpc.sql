create or replace function public.resolve_check(
    p_check_id uuid,
    p_rolls jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    pending_check public.pending_checks;
    resolved_payload jsonb;
    roll_total integer;
    check_total integer;
    check_success boolean;
begin
    if (select auth.uid()) is null then
        raise exception 'authenticated user is required';
    end if;

    select *
    into pending_check
    from public.pending_checks candidate
    where candidate.id = p_check_id
      and (select private.is_campaign_member(candidate.campaign_id));

    if pending_check.id is null then
        raise exception 'check is not available to this user';
    end if;

    if pending_check.status = 'resolved' then
        select event.payload
        into resolved_payload
        from public.game_events event
        where event.event_type = 'ability_check_resolved'
          and event.payload ->> 'check_id' = p_check_id::text
        order by event.created_at desc, event.id desc
        limit 1;
        if resolved_payload is null then
            raise exception 'resolved check result is missing';
        end if;
        return resolved_payload;
    end if;

    if pending_check.status <> 'pending' then
        raise exception 'check is no longer pending';
    end if;

    if p_rolls is null or jsonb_typeof(p_rolls) <> 'array' then
        raise exception 'rolls must be an array';
    end if;

    if jsonb_array_length(p_rolls) <> (pending_check.dice_spec ->> 'count')::integer then
        raise exception 'roll count does not match the check';
    end if;

    if exists (
        select 1
        from jsonb_array_elements(p_rolls) as roll(value)
        where case
            when jsonb_typeof(roll.value) <> 'number'
              or (roll.value #>> '{}') !~ '^[0-9]+$'
            then true
            else (roll.value #>> '{}')::numeric < 1
              or (roll.value #>> '{}')::numeric > (pending_check.dice_spec ->> 'sides')::numeric
        end
    ) then
        raise exception 'roll is outside the allowed range';
    end if;

    select coalesce(sum((roll.value #>> '{}')::integer), 0)
    into roll_total
    from jsonb_array_elements(p_rolls) as roll(value);
    check_total := roll_total + pending_check.modifier;
    check_success := check_total >= pending_check.difficulty;

    update public.pending_checks
    set status = 'resolved', resolved_at = now()
    where id = p_check_id
      and status = 'pending';

    if not found then
        select event.payload
        into resolved_payload
        from public.game_events event
        where event.event_type = 'ability_check_resolved'
          and event.payload ->> 'check_id' = p_check_id::text
        order by event.created_at desc, event.id desc
        limit 1;
        if resolved_payload is null then
            raise exception 'check resolution conflict';
        end if;
        return resolved_payload;
    end if;

    resolved_payload := jsonb_build_object(
        'check_id', pending_check.id,
        'label', initcap(pending_check.check_type) || ' Check',
        'dice', pending_check.dice_spec,
        'modifier', pending_check.modifier,
        'difficulty', pending_check.difficulty,
        'reason', pending_check.context,
        'rolls', p_rolls,
        'total', check_total,
        'success', check_success,
        'outcome', case when check_success then 'success' else 'failure' end,
        'status', 'resolved'
    );

    insert into public.game_events (campaign_id, character_id, event_type, payload)
    values (
        pending_check.campaign_id,
        pending_check.character_id,
        'ability_check_resolved',
        resolved_payload
    );

    return resolved_payload;
end;
$$;

revoke all on function public.resolve_check(uuid, jsonb) from public, anon;
grant execute on function public.resolve_check(uuid, jsonb) to authenticated;
