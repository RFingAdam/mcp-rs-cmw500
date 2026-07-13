"""Tests for RF band-plan data and the IMD engine (pure computation)."""

import pytest

from rs_cmw500_mcp.models.band_plans import (
    band_for_earfcn,
    ble_channel_to_freq_mhz,
    combination_allowed,
    earfcn_range,
    earfcn_to_frequencies,
    generate_ble_channels,
    generate_lte_earfcns,
    harmonic_products,
    intermod_products,
)


class TestBleChannels:
    def test_channel_to_freq(self):
        assert ble_channel_to_freq_mhz(0) == 2402.0
        assert ble_channel_to_freq_mhz(37) == 2476.0
        assert ble_channel_to_freq_mhz(39) == 2480.0

    def test_out_of_range(self):
        with pytest.raises(ValueError):
            ble_channel_to_freq_mhz(40)

    def test_generate_skips_advertising(self):
        chans = generate_ble_channels(1, 38, 1)
        assert 12 not in chans  # advertising channel excluded
        assert 1 in chans and 38 in chans
        assert chans == sorted(chans)
        assert len(chans) == 37  # 1..38 minus channel 12

    def test_generate_can_keep_advertising(self):
        chans = generate_ble_channels(10, 14, 1, skip_adv=False)
        assert 12 in chans


class TestEarfcn:
    def test_band_for_earfcn(self):
        assert band_for_earfcn(3100) == 7
        assert band_for_earfcn(300) == 1
        assert band_for_earfcn(999999) is None

    def test_earfcn_to_frequencies_band7(self):
        # Lowest EARFCN in band 7 -> band edges 2620 / 2500.
        band, dl, ul = earfcn_to_frequencies(2750)
        assert band == 7
        assert dl == 2620.0
        assert ul == 2500.0

    def test_earfcn_to_frequencies_offset_shared(self):
        # DL EARFCN 3100 -> offset 350 -> DL 2655, UL 2535 (both use DL offset).
        band, dl, ul = earfcn_to_frequencies(3100)
        assert band == 7
        assert dl == 2655.0
        assert ul == 2535.0  # regression guard for the corrected UL formula

    def test_earfcn_range(self):
        assert earfcn_range(7) == (2750, 3449)

    def test_generate_lte_earfcns_trims_edges(self):
        chans = generate_lte_earfcns(7, spacing=100, edge_trim=25)
        assert chans[0] == 2775  # 2750 + 25
        assert chans[-1] == 3424  # 3449 - 25, always included
        assert all(2750 <= c <= 3449 for c in chans)


class TestImdEngine:
    def test_intermod_order2(self):
        products = intermod_products(1000, 1000, 1200, 1200, max_order=2)
        centers = {round(p.center_mhz, 1) for p in products}
        assert centers == {200.0, 2200.0}  # |f1-f2| and |f1+f2|
        assert all(p.order == 2 for p in products)

    def test_intermod_order3_present(self):
        products = intermod_products(1000, 1000, 1200, 1200, max_order=3)
        order3 = {round(p.center_mhz, 1) for p in products if p.order == 3}
        assert {800.0, 1400.0, 3200.0, 3400.0} <= order3

    def test_intermod_bandwidth_aware(self):
        # bw1 = 20, bw2 = 10 -> order-2 product |1f1+1f2| bandwidth = 30.
        products = intermod_products(990, 1010, 1195, 1205, max_order=2)
        sum_prod = next(p for p in products if round(p.center_mhz) == 2200)
        assert sum_prod.bandwidth_mhz == pytest.approx(30.0)

    def test_harmonics(self):
        prods = harmonic_products(1000, 1000, max_order=3)
        centers = sorted(round(p.center_mhz) for p in prods)
        assert centers == [2000, 3000]

    def test_overlap(self):
        p = harmonic_products(900, 900, max_order=2)[0]  # 1800 MHz, bw 0
        assert p.overlaps(1790, 1810) is True
        assert p.overlaps(1900, 2000) is False


class TestConstraints:
    def test_no_lte_carrier_for_lte_victim(self):
        assert combination_allowed("LTE_B7", "WIFI_BLE_2G4", "LTE_B1") is False

    def test_no_dual_lte(self):
        assert combination_allowed("LTE_B7", "LTE_B12", "GNSS_L1") is False

    def test_no_wifi5_low_high(self):
        assert combination_allowed("WIFI5_LOW", "WIFI5_HIGH", "GNSS_L1") is False

    def test_no_halow_us_eu(self):
        assert combination_allowed("HALOW_US", "HALOW_EU", "GNSS_L1") is False

    def test_allowed_pair(self):
        assert combination_allowed("HALOW_US", "LTE_B12", "GNSS_L1") is True

    def test_none_profile_allows_everything(self):
        assert combination_allowed("LTE_B7", "LTE_B12", "LTE_B1", profile="none") is True
