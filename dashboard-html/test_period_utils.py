"""Synthetic period-selection regression tests; no company data."""
import unittest

from period_utils import select_visits, valid_month


def visit(month, n, sticker=None):
    return {
        "fechaVisita": f"{month}-15",
        "envioKobo": str(n),
        "codigoTienda": sticker or str(n),
        "respuestas": [],
    }


class PeriodSelectionTests(unittest.TestCase):
    def test_three_months(self):
        rows = [visit("2026-09", 1), visit("2026-10", 2), visit("2026-11", 3)]
        selected, months = select_visits(rows)
        self.assertEqual(len(selected), 3)
        self.assertEqual(months, ["2026-09", "2026-10", "2026-11"])

    def test_filter_exclusions_and_repeated_store_across_months(self):
        rows = [
            visit("2026-09", 1, "A"),
            visit("2026-10", 2, "A"),
            visit("2026-11", 3, "B"),
        ]
        selected, months = select_visits(rows, {"2"}, "2026-10", "2026-11")
        self.assertEqual([r["envioKobo"] for r in selected], ["3"])
        self.assertEqual(months, ["2026-11"])

    def test_duplicate_same_store_month_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "Tienda repetida"):
            select_visits([visit("2026-11", 1, "A"), visit("2026-11", 2, "A")])

    def test_invalid_range_and_month(self):
        with self.assertRaises(ValueError):
            select_visits([visit("2026-11", 1)], start_month="2026-12", end_month="2026-09")
        with self.assertRaises(ValueError):
            valid_month("2026-13")

    def test_empty_scope_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "No hay visitas"):
            select_visits([visit("2026-09", 1)], start_month="2026-11")

    def test_invalid_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "respuestas"):
            select_visits([{"fechaVisita":"2026-11-15","envioKobo":"1","codigoTienda":"A"}])


if __name__ == "__main__":
    unittest.main()
