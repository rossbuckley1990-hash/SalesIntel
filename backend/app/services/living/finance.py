"""Reproducible annual scenario model; independent of graphics and source updates."""

from decimal import Decimal, ROUND_HALF_UP

from app.schemas.living import ScenarioInput
from app.services.finance_summary import financial_year_months

PENNY = Decimal("0.01")


def money(value: Decimal) -> str:
    return str(value.quantize(PENNY, rounding=ROUND_HALF_UP))


def allocate(total: Decimal, count: int) -> list[Decimal]:
    """Allocate all pennies; final month absorbs only the rounding remainder."""
    if count == 0:
        return []
    part = (total / count).quantize(PENNY, rounding=ROUND_HALF_UP)
    return [part] * (count - 1) + [total - part * (count - 1)]


def calculate_scenario(inputs: ScenarioInput) -> dict:
    revenue = inputs.annual_revenue

    def case(share: Decimal, mobilisation: Decimal) -> dict:
        internal = revenue * share * inputs.inhouse_cost_ratio
        external = revenue * (1 - share) * inputs.subcontract_cost_ratio
        gross_margin = revenue - internal - external
        # Bid spend is incurred regardless of award; mobilisation only on award.
        contribution = (
            inputs.probability * (gross_margin - mobilisation) - inputs.bid_cost
        )
        return {
            "annual_revenue": money(revenue),
            "inhouse_cost": money(internal),
            "subcontract_cost": money(external),
            "gross_margin": money(gross_margin),
            "gross_margin_ratio": str(
                gross_margin / revenue if revenue else Decimal(0)
            ),
            "expected_contribution": money(contribution),
            "mobilisation_cost": money(mobilisation),
            "bid_cost": money(inputs.bid_cost),
            "working_capital_proxy": money(
                (internal + external) * Decimal(inputs.payment_delay_days) / 365
            ),
        }

    baseline = case(inputs.baseline_share, Decimal(0))
    proposed = case(inputs.proposed_share, inputs.mobilisation_cost)
    fy_months = financial_year_months(inputs.financial_year_start)
    start_year, start_month = (int(v) for v in inputs.start_month.split("-"))
    service_months = [
        f"{(start_year * 12 + start_month - 1 + i) // 12:04d}-{(start_year * 12 + start_month - 1 + i) % 12 + 1:02d}"
        for i in range(12)
    ]
    revenue_alloc = dict(zip(service_months, allocate(revenue, 12), strict=True))
    margin_alloc = dict(
        zip(
            service_months, allocate(Decimal(proposed["gross_margin"]), 12), strict=True
        )
    )
    monthly = [
        {
            "month": month,
            "revenue": money(revenue_alloc.get(month, Decimal(0))),
            "gross_margin": money(margin_alloc.get(month, Decimal(0))),
        }
        for month in fy_months
    ]
    sensitivity = []
    for offset in [Decimal("-0.05"), Decimal(0), Decimal("0.05")]:
        ratio = min(Decimal(1), max(Decimal(0), inputs.inhouse_cost_ratio + offset))
        gm = revenue * (
            1
            - inputs.proposed_share * ratio
            - (1 - inputs.proposed_share) * inputs.subcontract_cost_ratio
        )
        sensitivity.append(
            {
                "inhouse_cost_ratio": str(ratio),
                "gross_margin": money(gm),
                "expected_contribution": money(
                    inputs.probability * (gm - inputs.mobilisation_cost)
                    - inputs.bid_cost
                ),
            }
        )
    warnings = [
        "Hypothetical cost ratios and delivery shares require operational validation.",
        "Working capital is a cost × payment-delay proxy, not a cash-flow forecast.",
        "Scenario is annual; contract total value and approved LE1 remain separate.",
    ]
    if not any(m in fy_months for m in service_months):
        warnings.append(
            "The twelve-month service period does not overlap this financial year."
        )
    if inputs.proposed_share > inputs.baseline_share:
        warnings.append(
            "Confirm engineering capacity, accreditations and mobilisation before increasing self-delivery."
        )
    return {
        "model_version": "annual-delivery-v1",
        "currency": "GBP",
        "baseline": baseline,
        "proposed": proposed,
        "delta_gross_margin": money(
            Decimal(proposed["gross_margin"]) - Decimal(baseline["gross_margin"])
        ),
        "delta_expected_contribution": money(
            Decimal(proposed["expected_contribution"])
            - Decimal(baseline["expected_contribution"])
        ),
        "monthly": monthly,
        "financial_year_revenue": money(
            sum((Decimal(m["revenue"]) for m in monthly), Decimal(0))
        ),
        "sensitivity": sensitivity,
        "warnings": warnings,
        "formula": "GM = annual revenue × [1 − share × in-house cost ratio − (1 − share) × subcontract cost ratio]. Expected contribution = probability × (GM − mobilisation) − bid spend.",
    }
