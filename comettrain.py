#!/usr/bin/env python3
"""CometTrain - offline orbital period lookup, perihelion search and apparition calendar.

Three questions, three commands, no network and no files touched at runtime:

    list                          every comet in the embedded catalogue
    show <query>                  one comet: period, epoch, perihelion dates
    perihelion --date --window    which comets reach perihelion near a date
    calendar --from --days        everything coming up in a forward window

Standard library only: argparse, datetime, sys and textwrap.
"""

import argparse
import datetime
import sys
import textwrap

# --- calendar range -------------------------------------------------------
# datetime.date cannot exist outside 0001-01-01..9999-12-31, so every date
# computation runs on integer day numbers (proleptic Gregorian ordinals) and is
# only turned back into a date once it is proven to be inside the range.
MIN_ORDINAL = datetime.date.min.toordinal()  # 1
MAX_ORDINAL = datetime.date.max.toordinal()  # 3652059
BEFORE_TEXT = "before 0001-01-01"
AFTER_TEXT = "after 9999-12-31"

# Julian-year length; nominal catalogue periods are expressed in years.
DAYS_PER_YEAR = 365.2425

# Guard rails that keep a pathological flag value from stalling the terminal.
MAX_WINDOW_DAYS = 365250  # 1000 years either side of the reference date
MAX_SPAN_DAYS = 3652500  # ten thousand years of calendar window

# Widest comet name column used by the table and the apparition listings; the
# catalogue values are fixed today but a longer name must not break alignment.
NAME_COLUMN = 30


def _comet(name, aliases, period_years, epoch):
    """One catalogue record: a nominal orbit anchored on a known perihelion."""
    return {
        "name": name,
        "aliases": aliases,
        "period_years": period_years,
        "epoch": epoch,
    }


# The whole catalogue: name, aliases, nominal period in years, and one known
# perihelion (the orbit anchor). Periods are nominal values, not ephemerides.
CATALOGUE = (
    _comet("1P/Halley", ("Halley", "Halley's Comet"), 75.32, "1986-02-09"),
    _comet("2P/Encke", ("Encke",), 3.3088, "2017-03-10"),
    _comet("8P/Tuttle", ("Tuttle",), 13.61, "2021-08-27"),
    _comet("9P/Tempel 1", ("Tempel", "Tempel 1"), 5.52, "2016-08-02"),
    _comet("12P/Pons-Brooks", ("Pons-Brooks",), 70.60, "2024-04-21"),
    _comet("19P/Borrelly", ("Borrelly",), 6.85, "2022-02-01"),
    _comet("21P/Giacobini-Zinner", ("Giacobini-Zinner",), 6.62, "2018-09-10"),
    _comet("46P/Wirtanen", ("Wirtanen",), 5.43, "2018-12-12"),
    _comet("55P/Tempel-Tuttle", ("Tempel-Tuttle",), 33.24, "1998-02-28"),
    _comet("67P/Churyumov-Gerasimenko", ("Churyumov-Gerasimenko", "Churyumov"), 6.44, "2015-08-13"),
    _comet("73P/Schwassmann-Wachmann 3", ("Schwassmann-Wachmann",), 5.36, "2006-06-07"),
    _comet("81P/Wild 2", ("Wild", "Wild 2"), 6.41, "2010-02-23"),
    _comet("96P/Machholz", ("Machholz",), 5.29, "2017-10-27"),
    _comet("103P/Hartley 2", ("Hartley", "Hartley 2"), 6.46, "2010-10-28"),
    _comet("109P/Swift-Tuttle", ("Swift-Tuttle",), 133.28, "1992-12-11"),
    _comet("153P/Ikeya-Zhang", ("Ikeya-Zhang",), 366.50, "2002-03-18"),
    _comet("C/1995 [redacted] (Hale-Bopp)", ("Hale-Bopp",), 2533.00, "1997-04-01"),
    _comet("C/2011 L4 (PANSTARRS)", ("PANSTARRS",), 110000.00, "2013-03-10"),
    _comet("C/2014 UN271", ("Bernardinelli-Bernstein", "Bernardinelli"), 4500000.00, "2031-01-21"),
    _comet("C/2020 F3 (NEOWISE)", ("NEOWISE",), 4400.00, "2020-07-03"),
)

_EPOCH_CACHE = {}


def catalogue():
    """Return the embedded, read-only catalogue (single accessor for tests)."""
    return CATALOGUE


# --- dates ----------------------------------------------------------------


def parse_date(text):
    """Parse a strict YYYY-MM-DD calendar date; 2023-02-30 is rejected, not rolled over."""
    pieces = text.split("-")
    well_formed = (
        len(pieces) == 3
        and [len(piece) for piece in pieces] == [4, 2, 2]
        and all(piece.isdigit() for piece in pieces)
    )
    if not well_formed:
        raise argparse.ArgumentTypeError(
            "invalid date '{}': expected a real calendar date as YYYY-MM-DD".format(text)
        )
    try:
        return datetime.date(int(pieces[0]), int(pieces[1]), int(pieces[2]))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "invalid date '{}': {}".format(text, exc)
        ) from None


def day_text(day):
    """Render a day number as an ISO date, or as a sentinel outside 0001..9999."""
    if day < MIN_ORDINAL:
        return BEFORE_TEXT
    if day > MAX_ORDINAL:
        return AFTER_TEXT
    return datetime.date.fromordinal(day).isoformat()


def epoch_ordinal(comet):
    """Day number of the catalogue epoch (the known perihelion used as anchor)."""
    text = comet["epoch"]
    cached = _EPOCH_CACHE.get(text)
    if cached is None:
        cached = datetime.date.fromisoformat(text).toordinal()
        _EPOCH_CACHE[text] = cached
    return cached


# --- orbit arithmetic -----------------------------------------------------


def period_days(comet):
    """Nominal orbital period expressed in (fractional) days."""
    return comet["period_years"] * DAYS_PER_YEAR


def apparition_day(comet, orbit_index):
    """Day number of apparition k: epoch + k * period, rounded to a whole day."""
    return epoch_ordinal(comet) + int(round(orbit_index * period_days(comet)))


def nearest_orbit_index(comet, anchor_day):
    """Orbit index k whose apparition sits closest to anchor_day."""
    return int(round((anchor_day - epoch_ordinal(comet)) / period_days(comet)))


def apparitions(comet, anchor_day, span_days):
    """Every apparition (k, day number) within +/- span_days of anchor_day, ascending.

    The one shared orbit-selection helper: `show`, `perihelion` and `calendar`
    all route through it, so the views can never drift apart.
    """
    low = anchor_day - span_days
    high = anchor_day + span_days
    start = nearest_orbit_index(comet, anchor_day)
    found = []
    index = start
    while True:
        day = apparition_day(comet, index)
        if day < low:
            break
        if low <= day <= high:
            found.append((index, day))
        index -= 1
    index = start + 1
    while True:
        day = apparition_day(comet, index)
        if day > high:
            break
        if low <= day <= high:
            found.append((index, day))
        index += 1
    found.sort()
    return found


def nearest_apparition(comet, anchor_day):
    """Return (day number, orbit index) of the apparition closest to anchor_day."""
    start = nearest_orbit_index(comet, anchor_day)
    best_day = apparition_day(comet, start)
    best_index = start
    for index in (start - 1, start + 1):
        day = apparition_day(comet, index)
        if abs(day - anchor_day) < abs(best_day - anchor_day):
            best_day, best_index = day, index
    return best_day, best_index


def surrounding_apparitions(comet, anchor_day):
    """(previous, next) apparition day numbers bracketing anchor_day."""
    span = int(period_days(comet)) + 2
    window = apparitions(comet, anchor_day, span)
    previous = max((day for _, day in window if day <= anchor_day), default=None)
    following = min((day for _, day in window if day >= anchor_day), default=None)
    return previous, following


def today_ordinal():
    """Reference day for `show` and the default `calendar` window."""
    return datetime.date.today().toordinal()


# --- shared formatting ----------------------------------------------------


def name_column(comets):
    """Widest comet name to print, capped so a row stays inside 80 columns."""
    widest = max(len(comet["name"]) for comet in comets)
    return min(widest, NAME_COLUMN)


def short_name(name, width):
    """Keep a name on one line without pushing the following columns out."""
    return textwrap.shorten(name, width=width, placeholder="...")


def matches(comet, needle):
    """Case-insensitive substring match over the name and every alias."""
    if needle in comet["name"].casefold():
        return True
    return any(needle in alias.casefold() for alias in comet["aliases"])


def matched_comets(needle):
    """Catalogue order, de-duplicated: a comet listed once even if name and alias both match."""
    needle = needle.strip().casefold()
    if not needle:
        return []
    return [comet for comet in catalogue() if matches(comet, needle)]


# --- commands -------------------------------------------------------------


def cmd_list(args):
    """Print the whole catalogue as a fixed-width table."""
    comets = catalogue()
    width = name_column(comets)
    print("CometTrain catalogue - {} comets".format(len(comets)))
    print()
    print(
        "{:>3}  {:<{}}  {:>11}  {}".format(
            "#", "Name", width, "Period (yr)", "Catalogue epoch"
        )
    )
    print(
        "{:>3}  {:<{}}  {:>11}  {}".format(
            "---", "-" * width, width, "-" * 11, "-" * 15
        )
    )
    for position, comet in enumerate(comets, start=1):
        print(
            "{:>3}  {:<{}}  {:>11.2f}  {}".format(
                position,
                short_name(comet["name"], width),
                width,
                comet["period_years"],
                comet["epoch"],
            )
        )
    print()
    print("{} comets in the embedded catalogue.".format(len(comets)))
    return 0


def _day_or_unknown(day):
    """A bracketing date, or "unknown" if the orbit helper found none on that side."""
    return "unknown" if day is None else day_text(day)


def print_comet_detail(comet, reference_day):
    """The `show` detail block for exactly one comet."""
    previous, following = surrounding_apparitions(comet, reference_day)
    aliases = ", ".join(comet["aliases"]) if comet["aliases"] else "-"
    print(comet["name"])
    print("  aliases            : {}".format(aliases))
    print(
        "  period             : {:.2f} years ({} days)".format(
            comet["period_years"], int(round(period_days(comet)))
        )
    )
    print("  catalogue epoch    : {}".format(comet["epoch"]))
    print("  reference date     : {} (today)".format(day_text(reference_day)))
    print("  previous perihelion: {}".format(_day_or_unknown(previous)))
    print("  next perihelion    : {}".format(_day_or_unknown(following)))


def print_match_list(needle, comets):
    """Ambiguous `show`: every match with its period and epoch so the user can refine."""
    width = name_column(comets)
    print("{} comets match '{}':".format(len(comets), needle))
    print()
    for comet in comets:
        print(
            "  {:<{}}  {:>6.2f} yr  {}".format(
                short_name(comet["name"], width),
                width,
                comet["period_years"],
                comet["epoch"],
            )
        )
    print()
    print(
        'hint: refine the query, for example `python3 comettrain.py show "{}"`'.format(
            comets[0]["name"]
        )
    )


def cmd_show(args):
    """Detail block for one comet, or the list of matches for an ambiguous query."""
    found = matched_comets(args.query)
    if not found:
        print("no comet matched '{}'".format(args.query))
        print("hint: run `python3 comettrain.py list` to see every name in the catalogue")
        return 1
    if len(found) > 1:
        print_match_list(args.query, found)
        return 0
    print_comet_detail(found[0], today_ordinal())
    return 0


def cmd_perihelion(args):
    """Which catalogue comets reach perihelion inside +/- window of a date."""
    reference_day = args.date.toordinal()
    window = args.window
    rows = []
    skipped = []
    for comet in catalogue():
        day, _index = nearest_apparition(comet, reference_day)
        if not MIN_ORDINAL <= day <= MAX_ORDINAL:
            skipped.append(comet["name"])
            continue
        offset = day - reference_day
        if abs(offset) <= window:
            rows.append((abs(offset), offset, comet["name"], day))
    rows.sort()

    print(
        "Perihelion search around {} (day number {}), window +/- {} days".format(
            day_text(reference_day), reference_day, window
        )
    )
    print()
    if not rows:
        print("no comets within {} days of {}".format(window, day_text(reference_day)))
        print(
            "hint: widen the search with --window (for example --window {})".format(
                window * 4 + 30
            )
        )
    else:
        width = name_column(catalogue())
        print("{:<10}  {:<{}}  {:>8}".format("Date", "Comet", width, "Offset"))
        print("{:<10}  {:<{}}  {:>8}".format("-" * 10, "-" * width, width, "-" * 8))
        for _distance, offset, name, day in rows:
            print(
                "{:<10}  {:<{}}  {:>+8}".format(day_text(day), short_name(name, width), width, offset)
            )
        print()
        print("{} of {} comets listed.".format(len(rows), len(catalogue())))
    if skipped:
        print(
            "skipped {} comet(s): nearest apparition outside 0001-01-01..9999-12-31".format(
                len(skipped)
            )
        )
    return 0


def cmd_calendar(args):
    """Every apparition of every comet inside a forward window, ascending by date."""
    start_day = args.from_date.toordinal()
    requested_days = args.days
    end_day = start_day + requested_days
    truncated = end_day > MAX_ORDINAL
    if truncated:
        end_day = MAX_ORDINAL
    span = end_day - start_day

    rows = []
    for comet in catalogue():
        for _index, day in apparitions(comet, start_day, span):
            if start_day <= day <= end_day:
                rows.append((day, comet["name"]))
    rows.sort()

    print(
        "Apparition calendar - {} comets, {} to {} ({} days)".format(
            len(catalogue()),
            day_text(start_day),
            day_text(end_day),
            requested_days,
        )
    )
    print()
    if not rows:
        print("no apparitions in this window")
        print(
            "hint: raise --days to widen the window (for example --days {})".format(
                max(requested_days + 1, 366)
            )
        )
    else:
        width = name_column(catalogue())
        print("{:<10}  {:<{}}  {:>6}".format("Date", "Comet", width, "Days"))
        print("{:<10}  {:<{}}  {:>6}".format("-" * 10, "-" * width, width, "-" * 6))
        for day, name in rows:
            print(
                "{:<10}  {:<{}}  {:>6}".format(
                    day_text(day), short_name(name, width), width, day - start_day
                )
            )
        print()
        print("{} apparitions listed.".format(len(rows)))
    if truncated:
        print("window truncated at 9999-12-31")
    return 0


# --- command line ---------------------------------------------------------

ROOT_EXAMPLE = "Example: python3 comettrain.py show encke"
LIST_EXAMPLE = "Example: python3 comettrain.py list"
SHOW_EXAMPLE = 'Example: python3 comettrain.py show "halley\'s comet"'
PERIHELION_EXAMPLE = (
    "Example: python3 comettrain.py perihelion --date 2023-10-20 --window 30"
)
CALENDAR_EXAMPLE = "Example: python3 comettrain.py calendar --days 3650"


def window_days(text):
    """--window accepts a non-negative whole number of days."""
    return _bounded_int(text, 0, MAX_WINDOW_DAYS, "--window")


def calendar_days(text):
    """--days accepts at least one whole day."""
    return _bounded_int(text, 1, MAX_SPAN_DAYS, "--days")


def _bounded_int(text, low, high, flag):
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            "{} must be a whole number of days, got '{}'".format(flag, text)
        ) from None
    if not low <= value <= high:
        raise argparse.ArgumentTypeError(
            "{} must be between {} and {} days, got {}".format(flag, low, high, value)
        )
    return value


class CometTrainParser(argparse.ArgumentParser):
    """argparse, but an unknown subcommand points at --help instead of just dying."""

    def error(self, message):
        if "invalid choice" in message:
            message += " (run `comettrain --help` for the command list)"
        super().error(message)


def build_parser():
    """The five help surfaces: the root command and the four subcommands."""
    parser = CometTrainParser(
        prog="comettrain",
        description=textwrap.fill(
            "Offline comet lookup. Browse nominal orbital periods, find which "
            "catalogue comets reach perihelion near a date, and list the "
            "apparitions coming up in a forward window.",
            width=78,
        ),
        epilog=ROOT_EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version="comettrain 1.0.0"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    listing = subparsers.add_parser(
        "list",
        help="table of every comet with its period and catalogue epoch",
        description="Print the embedded catalogue as a fixed-width table.",
        epilog=LIST_EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    listing.set_defaults(handler=cmd_list)

    detail = subparsers.add_parser(
        "show",
        help="period, epoch and perihelion dates for one comet",
        description=textwrap.fill(
            "Look one comet up by a case-insensitive substring of its name or "
            "an alias and print its period, its catalogue epoch and the "
            "perihelion dates bracketing today.",
            width=78,
        ),
        epilog=SHOW_EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    detail.add_argument("query", metavar="QUERY", help="part of a name or alias, e.g. encke")
    detail.set_defaults(handler=cmd_show)

    near = subparsers.add_parser(
        "perihelion",
        help="comets reaching perihelion near a date",
        description=textwrap.fill(
            "Compute each comet's nearest apparition (epoch + k * period) and "
            "list the ones within +/- WINDOW days of DATE, nearest first.",
            width=78,
        ),
        epilog=PERIHELION_EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    near.add_argument(
        "--date",
        required=True,
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="reference date to search around",
    )
    near.add_argument(
        "--window",
        type=window_days,
        default=30,
        metavar="N",
        help="half-width of the search window in days (default: 30)",
    )
    near.set_defaults(handler=cmd_perihelion)

    upcoming = subparsers.add_parser(
        "calendar",
        help="apparitions coming up in a forward window",
        description=textwrap.fill(
            "List every apparition of every catalogue comet between FROM and "
            "FROM + DAYS, ascending by date.",
            width=78,
        ),
        epilog=CALENDAR_EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    upcoming.add_argument(
        "--from",
        dest="from_date",
        type=parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="start of the window (default: today)",
    )
    upcoming.add_argument(
        "--days",
        type=calendar_days,
        default=3650,
        metavar="N",
        help="length of the window in days (default: 3650)",
    )
    upcoming.set_defaults(handler=cmd_calendar)

    return parser


def main(argv=None):
    """Dispatch a command; 0 success, 1 no-match or internal error, 2 usage error."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    if handler is cmd_calendar and args.from_date is None:
        args.from_date = datetime.date.today()
    try:
        return handler(args)
    except Exception as exc:  # one clean line, never a traceback (see D6)
        detail = str(exc) or "no further detail"
        print(
            "comettrain: error: {}: {}".format(exc.__class__.__name__, detail),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
