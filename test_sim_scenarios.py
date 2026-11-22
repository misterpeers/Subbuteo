"""Focused tests for the headless scenario harness."""

import unittest

from sim_physics import (
    AWAY,
    HOME,
    PIECE_RADIUS_MM,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    Vector2,
)
from sim_scenarios import (
    ScenarioSetup,
    format_summary,
    random_setup,
    run_batch,
    run_scenario,
)


class ScenarioHarnessTests(unittest.TestCase):
    """Check reproducibility, team symmetry, and result reporting."""

    def test_random_setup_is_reproducible_and_non_overlapping(self) -> None:
        """The same seed gives the same setup, with no overlapping bodies."""
        first = random_setup(12)
        second = random_setup(12)
        positions = [*first.piece_positions, first.ball_position]

        self.assertEqual(first, second)
        for index, position in enumerate(positions):
            for other in positions[index + 1 :]:
                separation = Vector2(
                    (position.x - other.x) * PITCH_LENGTH_MM,
                    (position.y - other.y) * PITCH_WIDTH_MM,
                ).length
                self.assertGreaterEqual(separation, 2 * PIECE_RADIUS_MM)

    def test_away_setup_mirrors_the_home_setup(self) -> None:
        """Both teams face the same problem, reflected along X."""
        home = random_setup(5, HOME)
        away = random_setup(5, AWAY)

        self.assertAlmostEqual(away.ball_position.x, 1.0 - home.ball_position.x)
        self.assertAlmostEqual(away.ball_position.y, home.ball_position.y)

    def test_mirrored_seeds_make_the_same_opening_decisions(self) -> None:
        """Home and away results match seed for seed over a short horizon.

        Long sequences are not compared exactly, because mirroring rounds
        positions slightly and physics amplifies tiny differences.
        """
        home = run_batch(4, seed=100, team=HOME, max_flicks=3)
        away = run_batch(4, seed=100, team=AWAY, max_flicks=3)

        def shape(summary):
            """Reduce results to outcome, reason and flick count."""
            return {
                seed: (result.outcome, result.reason, result.flicks)
                for seed, result in summary.results.items()
            }

        self.assertEqual(shape(home), shape(away))

    def test_clear_shot_scenario_scores(self) -> None:
        """A piece beside the ball inside the shooting area scores."""
        result = run_scenario(
            ScenarioSetup(
                team=HOME,
                piece_positions=(Vector2(0.82, 0.5),),
                ball_position=Vector2(0.85, 0.5),
            )
        )

        self.assertEqual(result.outcome, "goal")

    def test_summary_reports_decision_counts_and_times(self) -> None:
        """Decision statistics add up and appear in the report."""
        summary = run_batch(3, seed=0, max_flicks=5)

        self.assertGreater(summary.decision_count, 0)
        self.assertEqual(
            summary.decision_count,
            summary.planned_decisions
            + summary.sampled_decisions
            + summary.no_move_decisions,
        )
        self.assertLessEqual(
            summary.decision_ms_percentile(50),
            summary.decision_ms_percentile(100),
        )
        self.assertIn("Decision time ms:", format_summary(summary))

    def test_percentile_rejects_values_outside_zero_to_one_hundred(self) -> None:
        """An invalid percentile is an error, not a silent clamp."""
        with self.assertRaises(ValueError):
            run_batch(1, seed=0, max_flicks=1).decision_ms_percentile(101)

    def test_summary_lists_outcomes_and_failing_seeds(self) -> None:
        """The report includes counts and the seeds needed to reproduce."""
        summary = run_batch(4, seed=0, max_flicks=6)
        report = format_summary(summary)

        self.assertEqual(summary.total, 4)
        self.assertIn("Goal rate:", report)
        self.assertEqual(
            sum(summary.outcomes.values()),
            summary.total,
        )
        if summary.failing_seeds():
            self.assertIn("First failing seeds:", report)


if __name__ == "__main__":
    unittest.main()
