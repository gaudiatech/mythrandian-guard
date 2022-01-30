from pkatagames_sdk.engine import enum_for_custom_event_types


MyEvTypes = enum_for_custom_event_types(
    'PlayerBuysItem',
    'WannaBuySkin',  # deprec
    'EquipOwnedSkin',  # deprec

    'FightStarts',

    'MissionStarts',  # contains t, idx
    'MissionEnds',  # contains idx

    'MissionFree',  # only for the view, contains idx

    'AvatarUpdate',  # only here to force view refresh itself
    'NotifyAutoloot'  # contains is_gold, amount
)