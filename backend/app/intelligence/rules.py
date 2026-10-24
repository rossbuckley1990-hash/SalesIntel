from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class BidRecommendation(StrEnum):
    PURSUE = "Pursue"
    PURSUE_WITH_EXECUTIVE_SPONSOR = "Pursue with executive sponsor"
    WATCH = "Watch"
    QUALIFY_OUT = "Qualify out"
    NO_BID = "No bid"


@dataclass(frozen=True)
class OpportunityIntelligenceInput:
    estimated_total_contract_value: float
    margin_percentage: float
    probability: float
    submission_deadline: date | None
    stage: str
    self_delivery_fit: str
    risk_rating: str
    strategic_fit_score: float


@dataclass(frozen=True)
class OpportunityIntelligenceResult:
    weighted_pipeline_value: float
    strategic_must_win: bool
    risk_rating: str
    margin_warning: bool
    deadline_warning: bool
    self_delivery_capture: bool
    executive_escalation: bool
    bid_no_bid_recommendation: BidRecommendation
    priority_score: float
    recommended_next_action: str


DEADLINE_WARNING_STAGES = {"itt live", "pricing", "final review"}
HIGH_SELF_DELIVERY_VALUES = {"high", "strong"}
RED_RISK_VALUES = {"red", "high", "high risk"}
AMBER_RISK_VALUES = {"amber", "medium", "medium risk"}
GREEN_RISK_VALUES = {"green", "low", "low risk"}
STRATEGIC_VALUE_THRESHOLD = 1_000_000
SELF_DELIVERY_CAPTURE_THRESHOLD = 250_000
EXECUTIVE_ESCALATION_THRESHOLD = 500_000


def calculate_opportunity_intelligence(
    opportunity: OpportunityIntelligenceInput,
    *,
    today: date | None = None,
) -> OpportunityIntelligenceResult:
    active_today = today or date.today()
    value = max(opportunity.estimated_total_contract_value, 0)
    margin_percentage = opportunity.margin_percentage
    probability_factor = _probability_factor(opportunity.probability)
    probability_percentage = probability_factor * 100
    weighted_pipeline_value = round(value * probability_factor, 2)

    strategic_must_win = value > STRATEGIC_VALUE_THRESHOLD and probability_percentage > 60
    margin_warning = margin_percentage < 25
    deadline_warning = _has_deadline_warning(opportunity, today=active_today)
    self_delivery_capture = (
        _normalise(opportunity.self_delivery_fit) in HIGH_SELF_DELIVERY_VALUES
        and value > SELF_DELIVERY_CAPTURE_THRESHOLD
    )
    calculated_risk_rating = _calculate_risk_rating(
        opportunity.risk_rating,
        margin_percentage=margin_percentage,
        deadline_warning=deadline_warning,
        value=value,
    )
    executive_escalation = (
        calculated_risk_rating == "Red" and value > EXECUTIVE_ESCALATION_THRESHOLD
    )
    bid_no_bid_recommendation = _recommend_bid_action(
        opportunity,
        calculated_risk_rating=calculated_risk_rating,
        value=value,
        strategic_must_win=strategic_must_win,
    )
    priority_score = _calculate_priority_score(
        weighted_pipeline_value=weighted_pipeline_value,
        strategic_fit_score=opportunity.strategic_fit_score,
        strategic_must_win=strategic_must_win,
        deadline_warning=deadline_warning,
        self_delivery_capture=self_delivery_capture,
        executive_escalation=executive_escalation,
        recommendation=bid_no_bid_recommendation,
    )

    return OpportunityIntelligenceResult(
        weighted_pipeline_value=weighted_pipeline_value,
        strategic_must_win=strategic_must_win,
        risk_rating=calculated_risk_rating,
        margin_warning=margin_warning,
        deadline_warning=deadline_warning,
        self_delivery_capture=self_delivery_capture,
        executive_escalation=executive_escalation,
        bid_no_bid_recommendation=bid_no_bid_recommendation,
        priority_score=priority_score,
        recommended_next_action=_recommended_next_action(
            recommendation=bid_no_bid_recommendation,
            margin_warning=margin_warning,
            deadline_warning=deadline_warning,
            self_delivery_capture=self_delivery_capture,
            executive_escalation=executive_escalation,
            strategic_must_win=strategic_must_win,
        ),
    )


def _probability_factor(probability: float) -> float:
    if probability <= 0:
        return 0
    if probability <= 1:
        return probability
    return min(probability / 100, 1)


def _has_deadline_warning(
    opportunity: OpportunityIntelligenceInput,
    *,
    today: date,
) -> bool:
    if opportunity.submission_deadline is None:
        return False
    return (
        _normalise(opportunity.stage) in DEADLINE_WARNING_STAGES
        and today <= opportunity.submission_deadline <= today + timedelta(days=14)
    )


def _calculate_risk_rating(
    stored_risk_rating: str,
    *,
    margin_percentage: float,
    deadline_warning: bool,
    value: float,
) -> str:
    normalised_risk = _normalise(stored_risk_rating)
    if normalised_risk in RED_RISK_VALUES or margin_percentage < 15:
        return "Red"
    if deadline_warning and value > EXECUTIVE_ESCALATION_THRESHOLD:
        return "Red"
    if normalised_risk in AMBER_RISK_VALUES or margin_percentage < 25 or deadline_warning:
        return "Amber"
    if normalised_risk in GREEN_RISK_VALUES:
        return "Green"
    return "Amber"


def _recommend_bid_action(
    opportunity: OpportunityIntelligenceInput,
    *,
    calculated_risk_rating: str,
    value: float,
    strategic_must_win: bool,
) -> BidRecommendation:
    if opportunity.margin_percentage < 15:
        return BidRecommendation.NO_BID
    if opportunity.strategic_fit_score < 45:
        return BidRecommendation.QUALIFY_OUT
    if calculated_risk_rating == "Red" and value > EXECUTIVE_ESCALATION_THRESHOLD:
        return BidRecommendation.PURSUE_WITH_EXECUTIVE_SPONSOR
    if opportunity.strategic_fit_score > 80 and opportunity.margin_percentage > 30:
        return BidRecommendation.PURSUE
    if strategic_must_win and calculated_risk_rating != "Red":
        return BidRecommendation.PURSUE
    if opportunity.margin_percentage < 25 or calculated_risk_rating == "Amber":
        return BidRecommendation.WATCH
    return BidRecommendation.PURSUE


def _calculate_priority_score(
    *,
    weighted_pipeline_value: float,
    strategic_fit_score: float,
    strategic_must_win: bool,
    deadline_warning: bool,
    self_delivery_capture: bool,
    executive_escalation: bool,
    recommendation: BidRecommendation,
) -> float:
    score = min(weighted_pipeline_value / 100_000, 30)
    score += min(max(strategic_fit_score, 0) * 0.25, 25)
    if strategic_must_win:
        score += 20
    if executive_escalation:
        score += 15
    if deadline_warning:
        score += 10
    if self_delivery_capture:
        score += 5
    if recommendation in {BidRecommendation.NO_BID, BidRecommendation.QUALIFY_OUT}:
        score -= 10
    return round(max(min(score, 100), 0), 2)


def _recommended_next_action(
    *,
    recommendation: BidRecommendation,
    margin_warning: bool,
    deadline_warning: bool,
    self_delivery_capture: bool,
    executive_escalation: bool,
    strategic_must_win: bool,
) -> str:
    if recommendation == BidRecommendation.NO_BID:
        return "No bid: margin is below the acceptable threshold for this pursuit."
    if recommendation == BidRecommendation.QUALIFY_OUT:
        return "Qualify out unless the strategic fit materially improves."
    if executive_escalation:
        return "Assign an executive sponsor and run a risk review before final commitment."
    if deadline_warning:
        return "Prioritise bid response activity and confirm submission ownership within 24 hours."
    if margin_warning:
        return "Review pricing, delivery assumptions and margin recovery options before progressing."
    if self_delivery_capture:
        return "Pursue and highlight self-delivery capture in the commercial strategy."
    if strategic_must_win:
        return "Pursue as a strategic must-win and confirm leadership action plan."
    if recommendation == BidRecommendation.PURSUE:
        return "Pursue and confirm the next commercial action with the opportunity owner."
    return "Watch and gather more evidence before committing bid resources."


def _normalise(value: str) -> str:
    return value.strip().lower().replace("_", " ")
