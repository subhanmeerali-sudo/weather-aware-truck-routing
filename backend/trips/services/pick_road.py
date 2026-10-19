"""
Picks the best road. the PDF says, in this order:
  1. fewest Severe miles
  2. fewest High miles
  3. lowest average risk
  4. shortest travel time
so we just sort by those 4 things. first one that is different decides the winner.
"""

TIE_MILES = 0.5  # half a mile difference is basically a tie (checkpoints arent THAT precise)
TIE_RISK = 0.001


def why_it_won(winner, runner_up):
    """writes a little sentence about why the winner beat 2nd place"""
    w, r = winner["summary"], runner_up["summary"]
    if abs(w["severe_miles"] - r["severe_miles"]) > TIE_MILES:
        return f"Fewest Severe miles ({w['severe_miles']:.0f} vs {r['severe_miles']:.0f} on {runner_up['label']})."
    if abs(w["high_miles"] - r["high_miles"]) > TIE_MILES:
        return f"Same Severe exposure, but fewer High-risk miles ({w['high_miles']:.0f} vs {r['high_miles']:.0f})."
    if abs(w["avg_risk"] - r["avg_risk"]) > TIE_RISK:
        return f"Similar Severe/High exposure, but lower average risk ({w['avg_risk']:.3f} vs {r['avg_risk']:.3f})."
    diff_min = (runner_up["duration_seconds"] - winner["duration_seconds"]) / 60
    return f"Weather risk is about the same, so the fastest route wins (saves {diff_min:.0f} min)."


def pick_best_road(roads):
    """
    we pick the road that is less scary. if theyre all the same scary, pick the fast one.
    uses tiny tie-breaks so 0.1 mile differences dont flip the answer.
    returns (sorted roads, reason text)
    """

    def fuzzy_key(road):
        # the sort key. smaller = better, like golf
        s = road["summary"]
        return (
            round(s["severe_miles"] / TIE_MILES),
            round(s["high_miles"] / TIE_MILES),
            round(s["avg_risk"] / TIE_RISK),
            road["duration_seconds"],
        )

    ranked = sorted(roads, key=fuzzy_key)
    for rank, road in enumerate(ranked, start=1):
        road["rank"] = rank
        road["recommended"] = rank == 1
    if len(ranked) == 1:
        reason = "Only one route was available."
    else:
        reason = why_it_won(ranked[0], ranked[1])
    if ranked[0]["summary"]["has_no_travel"]:
        reason += " Heads up: even this route has No Travel conditions, consider changing the departure time."
    return ranked, reason
