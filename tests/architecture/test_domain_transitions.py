import pytest

from SHARED.domain_transitions import InvalidTransition, transition_asset, transition_cartridge
from SHARED.models import Asset, AssetCondition, AssetStatus, Cartridge, CartridgeStatus


def cartridge(status):
    return Cartridge(marker_label="C", model="M", cabinet="1", status=status)


def asset(status):
    return Asset(inventory_number="I", name="PC", status=status, condition=AssetCondition.WORKING)


def test_cartridge_happy_path_and_invalid_skip():
    item = cartridge(CartridgeStatus.IN_USE)
    transition_cartridge(item, CartridgeStatus.PENDING_VENDOR)
    assert item.status == CartridgeStatus.PENDING_VENDOR
    with pytest.raises(InvalidTransition):
        transition_cartridge(item, CartridgeStatus.READY_FOR_PICKUP)


def test_cartridge_full_cycle():
    item = cartridge(CartridgeStatus.IN_USE)
    for target in (
        CartridgeStatus.PENDING_VENDOR,
        CartridgeStatus.AT_VENDOR,
        CartridgeStatus.READY_FOR_PICKUP,
        CartridgeStatus.IN_USE,
    ):
        transition_cartridge(item, target)
    assert item.status == CartridgeStatus.IN_USE
    assert item.condition == "working"


def test_asset_repair_cycle_and_decommission_terminal():
    item = asset(AssetStatus.AT_WORKPLACE)
    for target in (AssetStatus.PENDING_SC, AssetStatus.AT_SC, AssetStatus.RETURNED_IT, AssetStatus.AT_WORKPLACE):
        transition_asset(item, target)
    assert item.condition == AssetCondition.WORKING
    transition_asset(item, AssetStatus.DECOMMISSIONED)
    with pytest.raises(InvalidTransition):
        transition_asset(item, AssetStatus.AT_WORKPLACE)
