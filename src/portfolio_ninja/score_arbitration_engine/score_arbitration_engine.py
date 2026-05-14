import hashlib

from portfolio_ninja.domain.objects import RankedUniverse, ScoreSet


def rank_scores(score_set: ScoreSet) -> RankedUniverse:
    if not score_set.scores:
        raise ValueError("ScoreSet must not be empty")

    ranked = sorted(
        score_set.scores.items(),
        key=lambda item: (-item[1], item[0]),
    )

    params_hash = hashlib.sha256(
        f"{score_set.params_hash}|score_arbitration_engine_v1".encode()
    ).hexdigest()

    return RankedUniverse(
        ranked=[(ticker, score) for ticker, score in ranked],
        as_of_date=score_set.as_of_date,
        params_hash=params_hash,
        validation_status="valid",
        reason_codes=[],
    )
