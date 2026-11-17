"""The help texts of --no-billing-validation and --enable-cost-analysis each say
that the other flag is independent (A-45b): cost analysis still calls Cost
Explorer when billing validation is off."""

from inventag.cli.main import create_parser


def help_of(flag):
    for action in create_parser()._actions:
        if flag in action.option_strings:
            return " ".join(action.help.split())
    raise AssertionError(flag)


def test_billing_validation_help_names_cost_analysis_as_independent():
    text = help_of("--billing-validation")
    assert "--enable-cost-analysis is independent" in text
    assert "still calls Cost Explorer" in text


def test_cost_analysis_help_names_billing_validation_as_independent():
    text = help_of("--enable-cost-analysis")
    assert "--no-billing-validation is independent" in text
    assert "still calls Cost Explorer" in text
    assert text.startswith("Enable cost analysis and optimization recommendations")
