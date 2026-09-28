"""Domain state transitions shared by HTTP handlers and background jobs.

Transitions are deliberately explicit: callers may not assign lifecycle statuses arbitrarily.
The functions mutate the supplied ORM object but never commit; transaction ownership stays
with the application service/request boundary.
"""
from SHARED.models import Asset, AssetCondition, AssetStatus, Cartridge, CartridgeStatus


class InvalidTransition(ValueError):
    pass


CARTRIDGE_TRANSITIONS = {
    CartridgeStatus.IN_USE: {CartridgeStatus.PENDING_VENDOR},
    CartridgeStatus.PENDING_VENDOR: {CartridgeStatus.AT_VENDOR},
    CartridgeStatus.AT_VENDOR: {CartridgeStatus.READY_FOR_PICKUP},
    CartridgeStatus.READY_FOR_PICKUP: {CartridgeStatus.IN_USE},
}

ASSET_TRANSITIONS = {
    AssetStatus.AT_WORKPLACE: {AssetStatus.PENDING_SC, AssetStatus.DECOMMISSIONED},
    AssetStatus.PENDING_SC: {AssetStatus.AT_SC, AssetStatus.AT_WORKPLACE},
    AssetStatus.AT_SC: {AssetStatus.RETURNED_IT},
    AssetStatus.RETURNED_IT: {AssetStatus.AT_WORKPLACE, AssetStatus.PENDING_SC},
    AssetStatus.DECOMMISSIONED: set(),
}


def transition_cartridge(cartridge: Cartridge, target: CartridgeStatus) -> None:
    current = CartridgeStatus(cartridge.status)
    target = CartridgeStatus(target)
    if target == current:
        return
    if target not in CARTRIDGE_TRANSITIONS[current]:
        raise InvalidTransition(f"Invalid cartridge transition: {current.value} -> {target.value}")
    cartridge.status = target
    if target is CartridgeStatus.IN_USE:
        cartridge.condition = "working"
    elif target is CartridgeStatus.PENDING_VENDOR:
        cartridge.condition = "broken"


def transition_asset(asset: Asset, target: AssetStatus) -> None:
    current = AssetStatus(asset.status)
    target = AssetStatus(target)
    if target == current:
        return
    if target not in ASSET_TRANSITIONS[current]:
        raise InvalidTransition(f"Invalid asset transition: {current.value} -> {target.value}")
    asset.status = target
    if target is AssetStatus.AT_WORKPLACE:
        asset.condition = AssetCondition.WORKING
    elif target in {AssetStatus.PENDING_SC, AssetStatus.AT_SC}:
        asset.condition = AssetCondition.BROKEN
