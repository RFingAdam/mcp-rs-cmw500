"""Tests for the guided coexistence / RX prompts."""

import pytest

from rs_cmw500_mcp import prompts


def test_list_prompts():
    names = {p.name for p in prompts.list_prompts()}
    assert names == {
        "lte_ble_desense_sweep",
        "lte_wifi_coexistence_throughput",
        "rx_sensitivity_search",
        "imd_hit_analysis",
        "subghz_aggressor_sweep",
    }


def test_desense_prompt_weaves_args_and_names_tools():
    result = prompts.get_prompt("lte_ble_desense_sweep", {"lte_bands": "7, 20"})
    text = result.messages[0].content.text
    assert "7, 20" in text
    assert "cmw_coex_plan" in text
    assert "cmw_coex_validate_routing" in text


def test_imd_prompt_mentions_planner_tools():
    text = prompts.get_prompt("imd_hit_analysis", {"victim": "GNSS_L1"}).messages[0].content.text
    assert "cmw_imd_analyze" in text and "cmw_imd_batch" in text
    assert "GNSS_L1" in text


def test_every_prompt_renders():
    for p in prompts.list_prompts():
        result = prompts.get_prompt(p.name, {})
        assert result.messages
        assert result.messages[0].content.text


def test_unknown_prompt_raises():
    with pytest.raises(ValueError):
        prompts.get_prompt("does_not_exist")
