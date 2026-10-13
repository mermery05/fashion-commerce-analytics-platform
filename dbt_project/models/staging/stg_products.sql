with source as (

    select * from {{ source('bronze', 'products') }}

),

deduplicated as (

    select *
    from source
    qualify row_number() over (partition by id order by _ingested_at desc) = 1

),

flagged as (

    -- Completeness is judged on the RAW values, before any imputation below.
    select
        *,
        case
            when id is null or gender is null or masterCategory is null
              or subCategory is null or articleType is null or baseColour is null
              or season is null or year is null or usage is null
              or productDisplayName is null
            then 'Incomplete'
            else 'Complete'
        end as metadata_status
    from deduplicated

),

renamed as (

    select
        try_cast(id as integer)                      as product_id,
        nullif(trim(gender), '')                     as gender,
        {{ title_case('masterCategory') }}           as master_category,
        {{ title_case('subCategory') }}              as sub_category,
        {{ title_case('articleType') }}              as article_type,
        nullif(trim(baseColour), '')                 as base_colour,
        nullif(trim(season), '')                     as season,
        try_cast(year as integer)                    as year,
        nullif(trim(usage), '')                      as usage,
        nullif(trim(productDisplayName), '')         as product_display_name,
        metadata_status
    from flagged
    -- system test records
    where coalesce(trim(productDisplayName), '') not in ('RTV_LoadTest', 'test dispName')

),

usage_modes as (

    -- Most common usage per (sub_category, article_type), used to fill gaps
    select
        sub_category,
        article_type,
        mode(usage) as modal_usage
    from renamed
    where usage is not null
    group by 1, 2

),

brand_extracted as (

    select
        *,
        case
            when product_display_name is null then 'Unknown'
            -- brand = everything before the first audience word (Men, Women, ...)
            when regexp_matches(product_display_name,
                    ' (Men|Women|Unisex|Girls|Boys|Infants|Kids)\b', 'i')
                then trim(regexp_replace(product_display_name,
                    ' (Men|Women|Unisex|Girls|Boys|Infants|Kids)\b.*$', '', 'i'))
            else split_part(product_display_name, ' ', 1)
        end as brand_raw
    from renamed

),

brand_counted as (

    select
        *,
        count(*) over (partition by brand_raw) as brand_count
    from brand_extracted

),

brand_candidate as (

    -- brands seen fewer than 5 times are grouped as 'Other'
    select
        *,
        case when brand_count >= 5 then brand_raw else 'Other' end as brand_candidate
    from brand_counted

),

branded as (

    select
        *,
        replace(replace({{ title_case('brand_candidate') }}, '''S', ''), '''s', '') as brand_titled
    from brand_candidate

),

cleaned as (

    select
        b.product_id,
        b.gender,
        b.master_category,
        b.sub_category,
        b.article_type,

        -- colour: raw value, else a colour word found in the product name
        coalesce(
            b.base_colour,
            case
                when b.product_display_name ilike '%blue%'  then 'Blue'
                when b.product_display_name ilike '%black%' then 'Black'
                when b.product_display_name ilike '%red%'   then 'Red'
                when b.product_display_name ilike '%white%' then 'White'
                when b.product_display_name ilike '%grey%'  then 'Grey'
                when b.product_display_name ilike '%green%' then 'Green'
            end,
            'Unspecified'
        ) as base_colour,

        -- season: raw value, else keywords / industry codes (SS, FW, AH) in the name.
        -- Products without a year are 'Unspecified', as in the notebook.
        case
            when b.year is null                                        then 'Unspecified'
            when b.season is not null                                  then b.season
            when b.product_display_name ilike '%spring%'               then 'Spring'
            when b.product_display_name ilike '%summer%'               then 'Summer'
            when b.product_display_name ilike '%fall%'                 then 'Fall'
            when b.product_display_name ilike '%winter%'               then 'Winter'
            when regexp_matches(b.product_display_name, '\bSS\d*', 'i')           then 'Summer'
            when regexp_matches(b.product_display_name, '\bFW\d*|\bAH\d*', 'i')   then 'Fall'
            else 'Unspecified'
        end as season,

        -- Year stays NULL when unknown. (The pandas notebook used -1, which would
        -- silently skew any average or range filter.)
        b.year,

        coalesce(
            b.usage,
            case when b.master_category = 'Personal Care' then 'Casual' end,
            m.modal_usage,
            'Casual'
        ) as usage,

        case b.brand_titled
            when 'Red'       then 'Red Rose'
            when 'M Tv'      then 'MTV'
            when 'Fila Men'  then 'Fila'
            when 'Lee Women' then 'Lee'
            else b.brand_titled
        end as brand,

        b.product_display_name,
        b.metadata_status

    from branded b
    left join usage_modes m
        on  b.sub_category is not distinct from m.sub_category
        and b.article_type is not distinct from m.article_type

)

select
    product_id,
    gender,
    master_category,
    sub_category,
    article_type,
    base_colour,
    season,
    year,
    usage,
    brand,
    coalesce(
        product_display_name,
        gender || ' ' || base_colour || ' ' || article_type
    ) as product_display_name,
    metadata_status
from cleaned
