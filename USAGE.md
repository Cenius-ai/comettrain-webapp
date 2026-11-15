# Using CometTrain

Every command is read-only and offline. Run them from the project directory as
`python3 comettrain.py <command>`; the output below is verbatim.

## `list` — the catalogue

```bash
$ python3 comettrain.py list
CometTrain catalogue - 20 comets

  #  Name                        Period (yr)  Catalogue epoch
---  --------------------------  -----------  ---------------
  1  1P/Halley                         75.32  1986-02-09
  2  2P/Encke                           3.31  2017-03-10
  3  8P/Tuttle                         13.61  2021-08-27
  ...
 20  C/2020 F3 (NEOWISE)             4400.00  2020-07-03

20 comets in the embedded catalogue.
```

The period is the nominal orbital period in years; the epoch is one known
perihelion that anchors the orbit. Both columns stay aligned for every name and
every line fits inside 80 columns.

## `show <query>` — one comet in detail

`show` takes a case-insensitive substring of a name **or** an alias:

```bash
$ python3 comettrain.py show encke
2P/Encke
  aliases            : Encke
  period             : 3.31 years (1209 days)
  catalogue epoch    : 2017-03-10
  reference date     : 2026-11-16 (today)
  previous perihelion: 2023-10-22
  next perihelion    : 2027-02-12
```

Aliases are matched too, so `show "halley's comet"` finds `1P/Halley`. An ambiguous
query lists every match with its period and epoch so you can refine:

```bash
$ python3 comettrain.py show tempel
2 comets match 'tempel':

  9P/Tempel 1          5.52 yr  2016-08-02
  55P/Tempel-Tuttle   33.24 yr  1998-02-28

hint: refine the query, for example `python3 comettrain.py show "9P/Tempel 1"`
```

No match is a one-line message and exit code 1:

```bash
$ python3 comettrain.py show zzz
no comet matched 'zzz'
hint: run `python3 comettrain.py list` to see every name in the catalogue
[exit 1]
```

### Perihelia outside the calendar

CometTrain computes apparitions as day numbers, so a comet whose neighbouring
perihelion leaves 0001-01-01..9999-12-31 prints a sentinel rather than crashing:

```bash
$ python3 comettrain.py show bernardinelli
C/2014 UN271
  aliases            : Bernardinelli-Bernstein, Bernardinelli
  period             : 4500000.00 years (1643591250 days)
  catalogue epoch    : 2031-01-21
  reference date     : 2026-11-16 (today)
  previous perihelion: before 0001-01-01
  next perihelion    : 2031-01-21
```

`show hale` reports 1997-04-01 as the *previous* perihelion because that is the
nearest one on that side of today — the apparition before it (≈536 BC) is outside
the proleptic-Gregorian calendar and would print `before 0001-01-01` if it were the
bracketing date.

## `perihelion --date --window` — proximity search

```bash
$ python3 comettrain.py perihelion --date 2023-10-20 --window 30
Perihelion search around 2023-10-20 (day number 738813), window +/- 30 days

Date        Comet                         Offset
----------  --------------------------  --------
2023-10-22  2P/Encke                          +2
2023-09-29  103P/Hartley 2                   -21

2 of 20 comets listed.
```

Each comet's *nearest* apparition is computed as `epoch + k × period`, which is why
Encke shows up with `+2` days even though its catalogue epoch is 2017-03-10. Rows
are sorted by absolute offset, the offset is signed, and comets whose nearest
apparition would leave the calendar are counted in the footer:

```bash
$ python3 comettrain.py perihelion --date 0001-01-05 --window 3
Perihelion search around 0001-01-05 (day number 5), window +/- 3 days

no comets within 3 days of 0001-01-05
hint: widen the search with --window (for example --window 42)
skipped 6 comet(s): nearest apparition outside 0001-01-01..9999-12-31
```

An impossible date is a usage error, not a rollover:

```bash
$ python3 comettrain.py perihelion --date 2023-02-30 --window 30
usage: comettrain perihelion [-h] --date YYYY-MM-DD [--window N]
comettrain perihelion: error: argument --date: invalid date '2023-02-30': day is out of range for month
[exit 2]
```

## `calendar --from --days` — forward window

```bash
$ python3 comettrain.py calendar --from 2026-01-01 --days 1095
Apparition calendar - 20 comets, 2026-01-01 to 2028-12-31 (1095 days)

Date        Comet                         Days
----------  --------------------------  ------
2027-02-12  2P/Encke                       407
2027-08-17  9P/Tempel 1                    593
2027-11-15  73P/Schwassmann-Wachmann 3     683
2028-05-26  96P/Machholz                   876
...
```

The 2P/Encke line above is the same 2027-02-12 date `show encke` prints as its
*next* perihelion: both go through one orbit-selection helper, so the two views can
never disagree.

`--from` defaults to today and `--days` to 3650. An empty window prints a hint
instead of an error, and a window that runs past the end of the calendar is
truncated:

```bash
$ python3 comettrain.py calendar --from 9999-12-01 --days 365
Apparition calendar - 20 comets, 9999-12-01 to 9999-12-31 (365 days)

no apparitions in this window
hint: raise --days to widen the window (for example --days 366)
window truncated at 9999-12-31
```

## `--help` — the fifth surface

Every command has its own help screen, each ending in a runnable example:

```bash
$ python3 comettrain.py perihelion --help
...
Example: python3 comettrain.py perihelion --date 2023-10-20 --window 30
```

Unknown commands exit 2 and point at the help:

```bash
$ python3 comettrain.py frobnicate
usage: comettrain [-h] [--version] <command> ...
comettrain: error: argument <command>: invalid choice: 'frobnicate' (choose from 'list', 'show', 'perihelion', 'calendar') (run `comettrain --help` for the command list)
[exit 2]
```

## Scripting it

Results go to stdout, diagnostics to stderr, and the exit codes are stable
(0 success, 1 no-match/internal error, 2 usage), so the tool composes in a shell:

```bash
python3 comettrain.py calendar --days 730 | awk '$1 >= "2026-01-01"'
python3 comettrain.py show encke | grep 'next perihelion'
```
