"""Smoke suite for CometTrain - standard library unittest only.

Run with:  python3 -m unittest discover -s tests
       or:  python3 -m pytest tests
"""

import contextlib
import datetime
import io
import pathlib
import shlex
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import comettrain  # noqa: E402  (path fix-up has to run first)


def run_cli(*argv):
    """Run comettrain.main with captured streams: returns (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = comettrain.main(list(argv))
        except SystemExit as exc:  # argparse's own exit path (usage errors, --version)
            code = exc.code if isinstance(exc.code, int) else 0
    return code, out.getvalue(), err.getvalue()


def comet(name):
    """Look a catalogue entry up by its exact name."""
    for entry in comettrain.catalogue():
        if entry["name"] == name:
            return entry
    raise AssertionError("missing catalogue entry: {}".format(name))


class StandaloneTest(unittest.TestCase):
    def test_imports_are_standard_library_only(self):
        source = pathlib.Path(comettrain.__file__).read_text(encoding="utf-8")
        imports = [
            line.strip()
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        self.assertEqual(
            imports, ["import argparse", "import datetime", "import sys", "import textwrap"]
        )

    def test_no_runtime_writes_or_network_calls(self):
        source = pathlib.Path(comettrain.__file__).read_text(encoding="utf-8")
        for forbidden in ("open(", "socket", "urllib", "requests", "sqlite3", "os."):
            self.assertNotIn(forbidden, source)


class CatalogueTest(unittest.TestCase):
    def test_catalogue_is_populated_and_well_formed(self):
        comets = comettrain.catalogue()
        self.assertGreaterEqual(len(comets), 16)
        names = [entry["name"] for entry in comets]
        self.assertEqual(len(names), len(set(names)))
        for entry in comets:
            self.assertGreater(entry["period_years"], 0)
            epoch = datetime.date.fromisoformat(entry["epoch"])
            self.assertGreaterEqual(epoch.toordinal(), comettrain.MIN_ORDINAL)
            self.assertLessEqual(epoch.toordinal(), comettrain.MAX_ORDINAL)

    def test_halley_is_present_with_period_and_epoch(self):
        halley = comet("1P/Halley")
        self.assertAlmostEqual(halley["period_years"], 75.32, places=2)
        self.assertEqual(halley["epoch"], "1986-02-09")


class RangeGuardTest(unittest.TestCase):
    def test_day_text_sentinels(self):
        self.assertEqual(comettrain.day_text(0), "before 0001-01-01")
        self.assertEqual(comettrain.day_text(-500000), "before 0001-01-01")
        self.assertEqual(comettrain.day_text(comettrain.MAX_ORDINAL + 1), "after 9999-12-31")
        self.assertEqual(comettrain.day_text(comettrain.MIN_ORDINAL), "0001-01-01")
        self.assertEqual(comettrain.day_text(738813), "2023-10-20")

    def test_long_period_apparitions_never_construct_bad_dates(self):
        for entry in comettrain.catalogue():
            for index in (-3, -1, 0, 1, 3):
                day = comettrain.apparition_day(entry, index)
                self.assertIsInstance(comettrain.day_text(day), str)

    def test_show_of_future_epoch_comet_reports_before_sentinel(self):
        code, out, err = run_cli("show", "bernardinelli")
        self.assertEqual(code, 0)
        self.assertIn("before 0001-01-01", out)
        self.assertIn("2031-01-21", out)
        self.assertNotIn("Traceback", err)


class NearestApparitionTest(unittest.TestCase):
    def test_nearest_apparition_finds_encke_2023_even_though_epoch_is_2017(self):
        encke = comet("2P/Encke")
        anchor = datetime.date(2023, 10, 20).toordinal()
        day, _index = comettrain.nearest_apparition(encke, anchor)
        self.assertEqual(day, datetime.date(2023, 10, 22).toordinal())
        self.assertEqual(day - anchor, 2)

    def test_orbit_index_is_the_nearest_multiple_of_the_period(self):
        encke = comet("2P/Encke")
        epoch = comettrain.epoch_ordinal(encke)
        period = comettrain.period_days(encke)
        self.assertEqual(comettrain.nearest_orbit_index(encke, epoch), 0)
        self.assertEqual(comettrain.nearest_orbit_index(encke, epoch + int(period * 3) + 3), 3)

    def test_apparitions_stay_inside_the_requested_window(self):
        encke = comet("2P/Encke")
        anchor = datetime.date(2023, 10, 20).toordinal()
        window = comettrain.apparitions(encke, anchor, 1210)
        self.assertEqual([index for index, _day in window], [1, 2])
        for _index, day in window:
            self.assertLessEqual(abs(day - anchor), 1210)
        self.assertEqual([day for _, day in window], sorted(day for _, day in window))

    def test_show_and_calendar_agree_on_the_next_apparition(self):
        encke = comet("2P/Encke")
        previous, following = comettrain.surrounding_apparitions(
            encke, datetime.date.today().toordinal()
        )
        self.assertLessEqual(previous, datetime.date.today().toordinal())
        self.assertGreaterEqual(following, datetime.date.today().toordinal())
        self.assertAlmostEqual(
            (following - previous) / comettrain.DAYS_PER_YEAR, 3.31, places=1
        )


class ListCommandTest(unittest.TestCase):
    def test_list_prints_every_comet_in_aligned_columns(self):
        code, out, err = run_cli("list")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("Period (yr)", out)
        self.assertIn("Catalogue epoch", out)
        for entry in comettrain.catalogue():
            self.assertIn(entry["name"], out)
        self.assertIn("1P/Halley", out)
        self.assertIn("1986-02-09", out)
        self.assertIn("{} comets in the embedded catalogue".format(len(comettrain.catalogue())), out)

    def test_list_lines_fit_eighty_columns_and_columns_line_up(self):
        _code, out, _err = run_cli("list")
        self.assertTrue(all(len(line) <= 80 for line in out.splitlines()))
        rows = [
            line
            for line in out.splitlines()
            if line[:3].strip().isdigit() and line[3:5] == "  "
        ]
        self.assertEqual(len(rows), len(comettrain.catalogue()))
        epoch_columns = {line.index(entry["epoch"]) for line, entry in zip(rows, comettrain.catalogue())}
        self.assertEqual(len(epoch_columns), 1)

    def test_long_name_row_stays_on_one_line(self):
        _code, out, _err = run_cli("list")
        row = next(line for line in out.splitlines() if "NEOWISE" in line)
        self.assertIn("2020-07-03", row)
        self.assertEqual(len(row), len(row.rstrip()))


class ShowCommandTest(unittest.TestCase):
    def test_show_encke_prints_period_epoch_and_bracketing_dates(self):
        code, out, err = run_cli("show", "encke")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("2P/Encke", out)
        self.assertIn("3.31 years", out)
        self.assertIn("2017-03-10", out)
        self.assertIn("previous perihelion:", out)
        self.assertIn("next perihelion    :", out)

    def test_show_matches_aliases_case_insensitively(self):
        code, out, _err = run_cli("show", "halley's comet")
        self.assertEqual(code, 0)
        self.assertIn("1P/Halley", out)
        self.assertIn("Halley's Comet", out)

    def test_show_ambiguous_query_lists_every_match(self):
        code, out, _err = run_cli("show", "tempel")
        self.assertEqual(code, 0)
        self.assertIn("2 comets match 'tempel'", out)
        self.assertIn("9P/Tempel 1", out)
        self.assertIn("55P/Tempel-Tuttle", out)
        self.assertIn("hint: refine the query", out)

    def test_show_without_match_exits_one(self):
        code, out, _err = run_cli("show", "zzz")
        self.assertEqual(code, 1)
        self.assertIn("no comet matched 'zzz'", out)
        self.assertIn("python3 comettrain.py list", out)

    def test_show_is_deterministic(self):
        first = run_cli("show", "encke")
        second = run_cli("show", "encke")
        self.assertEqual(first, second)


class PerihelionCommandTest(unittest.TestCase):
    def test_encke_is_found_with_a_plus_two_day_offset(self):
        code, out, _err = run_cli("perihelion", "--date", "2023-10-20", "--window", "30")
        self.assertEqual(code, 0)
        self.assertIn("2023-10-20", out)
        self.assertIn("738813", out)
        self.assertIn("+/- 30 days", out)
        encke_row = next(line for line in out.splitlines() if "2P/Encke" in line)
        self.assertIn("+2", encke_row)

    def test_rows_are_sorted_by_absolute_offset(self):
        _code, out, _err = run_cli("perihelion", "--date", "2023-10-20", "--window", "60")
        offsets = [
            int(line.rsplit(None, 1)[-1])
            for line in out.splitlines()
            if line[:4].isdigit() and line[:10].count("-") == 2
        ]
        self.assertGreaterEqual(len(offsets), 2)
        self.assertEqual(offsets, sorted(offsets, key=abs))
        self.assertTrue(any(offset < 0 for offset in offsets))
        self.assertTrue(any(offset > 0 for offset in offsets))

    def test_empty_window_exits_zero_with_a_hint(self):
        code, out, _err = run_cli("perihelion", "--date", "2024-06-30", "--window", "1")
        self.assertEqual(code, 0)
        self.assertIn("no comets within 1 days of 2024-06-30", out)
        self.assertIn("--window", out)

    def test_low_reference_date_reports_skipped_comets(self):
        code, out, err = run_cli("perihelion", "--date", "0001-01-05", "--window", "3")
        self.assertEqual(code, 0)
        self.assertIn("skipped ", out)
        self.assertIn("outside 0001-01-01..9999-12-31", out)
        self.assertNotIn("Traceback", err)

    def test_impossible_date_is_a_usage_error(self):
        code, out, err = run_cli("perihelion", "--date", "2023-02-30", "--window", "30")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("invalid date '2023-02-30'", err)
        self.assertNotIn("Traceback", err)

    def test_bad_window_is_a_usage_error(self):
        for value in ("abc", "-5"):
            with self.subTest(window=value):
                code, _out, err = run_cli(
                    "perihelion", "--date", "2024-01-01", "--window", value
                )
                self.assertEqual(code, 2)
                self.assertIn("--window", err)
                self.assertNotIn("Traceback", err)


class CalendarCommandTest(unittest.TestCase):
    def test_default_window_is_today_plus_3650_days(self):
        code, out, _err = run_cli("calendar")
        self.assertEqual(code, 0)
        self.assertIn(datetime.date.today().isoformat(), out)
        self.assertIn("3650 days", out)
        self.assertIn("apparitions listed", out)

    def test_rows_ascend_by_date(self):
        _code, out, _err = run_cli("calendar", "--from", "2024-01-01", "--days", "2000")
        dates = [
            line[:10]
            for line in out.splitlines()
            if line[:4].isdigit() and line[:10].count("-") == 2
        ]
        self.assertGreaterEqual(len(dates), 3)
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(len(set(dates[:2])), 2 if dates[0] != dates[1] else 1)

    def test_first_calendar_apparition_matches_show_next(self):
        _code, shown, _err = run_cli("show", "encke")
        next_line = next(line for line in shown.splitlines() if "next perihelion" in line)
        next_date = next_line.rsplit(None, 1)[-1]
        code, listing, _err = run_cli(
            "calendar", "--from", datetime.date.today().isoformat(), "--days", "4000"
        )
        self.assertEqual(code, 0)
        first_encke = next(line for line in listing.splitlines() if "2P/Encke" in line)
        self.assertEqual(first_encke[:10], next_date)

    def test_empty_window_exits_zero(self):
        code, out, _err = run_cli("calendar", "--from", "2024-05-15", "--days", "1")
        self.assertEqual(code, 0)
        self.assertIn("no apparitions in this window", out)
        self.assertIn("--days", out)

    def test_window_past_9999_is_truncated_without_a_traceback(self):
        code, out, err = run_cli("calendar", "--from", "9999-12-01", "--days", "365")
        self.assertEqual(code, 0)
        self.assertIn("window truncated at 9999-12-31", out)
        self.assertNotIn("Traceback", err)


class HelpCommandTest(unittest.TestCase):
    SURFACES = (
        ("--help",),
        ("list", "--help"),
        ("show", "--help"),
        ("perihelion", "--help"),
        ("calendar", "--help"),
    )

    def test_every_surface_prints_a_runnable_example(self):
        for argv in self.SURFACES:
            with self.subTest(surface=" ".join(argv)):
                code, out, _err = run_cli(*argv)
                self.assertEqual(code, 0)
                examples = [
                    line for line in out.splitlines() if line.startswith("Example: ")
                ]
                self.assertEqual(len(examples), 1)
                command = examples[0][len("Example: "):]
                tokens = shlex.split(command)
                self.assertEqual(tokens[:2], ["python3", "comettrain.py"])
                run_code, _run_out, run_err = run_cli(*tokens[2:])
                self.assertEqual(run_code, 0)
                self.assertEqual(run_err, "")

    def test_bare_invocation_prints_usage_and_exits_zero(self):
        code, out, _err = run_cli()
        self.assertEqual(code, 0)
        self.assertIn("usage: comettrain", out)

    def test_version_flag(self):
        code, out, err = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertIn("comettrain", out)
        self.assertEqual(err, "")


class ExitCodeContractTest(unittest.TestCase):
    def test_unknown_subcommand_exits_two_and_points_at_help(self):
        code, _out, err = run_cli("frobnicate")
        self.assertEqual(code, 2)
        self.assertIn("invalid choice", err)
        self.assertIn("--help", err)

    def test_internal_failure_is_one_line_on_stderr_with_status_one(self):
        with mock.patch.object(comettrain, "catalogue", side_effect=RuntimeError("boom")):
            code, out, err = run_cli("list")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        lines = err.strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("comettrain: error: "))
        self.assertIn("boom", lines[0])
        self.assertNotIn("Traceback", err)

    def test_success_no_match_and_usage_codes(self):
        self.assertEqual(run_cli("list")[0], 0)
        self.assertEqual(run_cli("show", "zzz")[0], 1)
        self.assertEqual(run_cli("show")[0], 2)


class DocsTest(unittest.TestCase):
    def test_readme_quotes_every_help_example_verbatim(self):
        readme = (pathlib.Path(comettrain.__file__).parent / "README.md").read_text(
            encoding="utf-8"
        )
        for argv in HelpCommandTest.SURFACES:
            _code, out, _err = run_cli(*argv)
            example = next(
                line for line in out.splitlines() if line.startswith("Example: ")
            )
            command = example[len("Example: "):]
            with self.subTest(surface=command):
                self.assertIn(command, readme)

    def test_transcript_records_the_required_surfaces(self):
        transcript = (
            pathlib.Path(comettrain.__file__).parent / "demo" / "transcript.txt"
        ).read_text(encoding="utf-8")
        for expected in (
            "$ python3 comettrain.py list",
            "$ python3 comettrain.py show encke",
            "$ python3 comettrain.py show hale",
            "$ python3 comettrain.py perihelion --date 2023-10-20 --window 30",
            "$ python3 comettrain.py calendar --days 3650",
            "$ python3 comettrain.py --help",
            "$ python3 comettrain.py perihelion --date 2023-02-30 --window 30",
            "$ python3 comettrain.py show zzz",
            "[exit 1]",
            "[exit 2]",
        ):
            self.assertIn(expected, transcript)


if __name__ == "__main__":
    unittest.main()
