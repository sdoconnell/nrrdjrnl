#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nrrdjrnl
Version:  0.0.2
Author:   Sean O'Connell <sean@sdoconnell.net>
License:  MIT
Homepage: https://github.com/sdoconnell/nrrdjrnl
About:
A terminal-based journal management tool with local file-based storage.

usage: nrrdjrnl [-h] [-c <file>] for more help: nrrdjrnl <command> -h ...

Terminal-based journal management for nerds.

commands:
  (for more help: nrrdjrnl <command> -h)
    delete (rm)         delete an entry file
    list (ls)           list entries
    open                open a journal entry
    search              search entries
    shell               interactive shell
    version             show version info

optional arguments:
  -h, --help            show this help message and exit
  -c <file>, --config <file>
                        config file


Copyright © 2021 Sean O'Connell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import argparse
import calendar
import configparser
import os
import re
import subprocess
import sys
from cmd import Cmd
from datetime import datetime, timedelta, date

import tzlocal
from dateutil import parser as dtparser
from rich import box
from rich.color import ColorParseError
from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text
from rich.style import Style
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

APP_NAME = "nrrdjrnl"
APP_VERS = "0.0.2"
APP_COPYRIGHT = "Copyright © 2021 Sean O'Connell."
APP_LICENSE = "Released under MIT license."
DEFAULT_DATA_DIR = f"$HOME/.local/share/{APP_NAME}"
DEFAULT_CONFIG_FILE = f"$HOME/.config/{APP_NAME}/config"
DEFAULT_FIRST_WEEKDAY = 6
DEFAULT_CONFIG = (
    "[main]\n"
    f"data_dir = {DEFAULT_DATA_DIR}\n"
    "# file extension for journal files (e.g. 'md' for\n"
    "# markdown. don't include the '.' character. the default\n"
    "# is no extension.\n"
    "#file_ext =\n"
    "# options to be used when editing the file for the\n"
    "# current day (e.g., '\"+normal G$\" +startinsert' to\n"
    "# instruct vim/neovim move to the last line and go into\n"
    "# INSERT mode when the file is opened)\n"
    "#today_options =\n"
    "# file with which to populate new journal entries\n"
    "# for the current day. e.g., this file may be generated\n"
    "# by a daily cronjob or other script to pre-populate a\n"
    "# new journal entry with the day's events or other info.\n"
    "#today_template =\n"
    "# first day of week (0 = Mon, 6 = Sun)\n"
    f"first_weekday = {DEFAULT_FIRST_WEEKDAY}\n"
    "# show calendars in week, month and year list views\n"
    "show_calendar_week = true\n"
    "show_calendar_month = true\n"
    "show_calendar_year = true\n"
    "\n"
    "[colors]\n"
    "disable_colors = false\n"
    "disable_bold = false\n"
    "# set to 'true' if your terminal pager supports color\n"
    "# output and you would like color output when using\n"
    "# the '--pager' ('-p') option\n"
    "color_pager = false\n"
    "# custom colors\n"
    "#title = blue\n"
    "#calendar = bright_cyan\n"
    "#calendar_hl = yellow\n"
    "#border = white\n"
    "#date = green\n"
    "#dateheader = blue\n"
)


class Entries():
    """Performs journal entry operations.

    Attributes:
        config_file (str):  application config file.
        data_dir (str):     directory containing journal entry files.
        dflt_config (str):  the default config if none is present.

    """
    def __init__(
            self,
            config_file,
            data_dir,
            dflt_config):
        """Initializes an Events() object."""
        self.config_file = config_file
        self.data_dir = data_dir
        self.config_dir = os.path.dirname(self.config_file)
        self.dflt_config = dflt_config
        self.interactive = False

        # default colors
        self.color_title = "bright_blue"
        self.color_border = "white"
        self.color_date = "green"
        self.color_dateheader = "blue"
        self.color_calendar = "bright_cyan"
        self.color_calendar_hl = "yellow"
        self.color_bold = True
        self.color_pager = False

        # editor (required for some functions)
        self.editor = os.environ.get("EDITOR")

        # defaults
        self.ltz = tzlocal.get_localzone()
        self.first_weekday = DEFAULT_FIRST_WEEKDAY
        self.show_calendar_week = True
        self.show_calendar_month = True
        self.show_calendar_year = True
        self.file_ext = None
        self.today_options = None
        self.today_template = None

        # initial style definitions, these are updated after the config
        # file is parsed for custom colors
        self.style_title = None
        self.style_border = None
        self.style_date = None
        self.style_dateheader = None
        self.style_calendar = None
        self.style_calendar_hl = None

        self._default_config()
        self._parse_config()
        self._verify_data_dir()
        self._parse_files()

    def _create_entry(self, dateobj):
        """Creates a new journal file for a date.

        Args:
            dateobj (obj): datetime date object.

        Returns:
            success (bool): creation was successful.

        """
        success = False
        datetxt = str(dateobj)
        if self.file_ext:
            date_file = os.path.join(
                    self.data_dir, f"{datetxt}.{self.file_ext}")
        else:
            date_file = os.path.join(self.data_dir, datetxt)

        headline = dateobj.strftime("Journal for %A, %Y-%m-%d")
        default_template = f"{headline}\n\nToday:\n"

        try:
            with open(date_file, 'w') as t_file:
                t_file.write(default_template)
        except (IOError, OSError):
            pass
        else:
            self.refresh()
            success = True
        return success

    def _create_today(self):
        """Creates a new journal file for today, using a template if one
        has been specified.

        Returns:
            success (bool): creation was successful.

        """
        success = False
        today = str(date.today())
        if self.file_ext:
            today_file = os.path.join(
                    self.data_dir, f"{today}.{self.file_ext}")
        else:
            today_file = os.path.join(self.data_dir, today)

        headline = datetime.now(
            tz=self.ltz).strftime("Journal for %A, %Y-%m-%d")
        default_template = f"{headline}\n\nToday:\n"

        if not self.today_template:
            template = default_template
        else:
            try:
                with open(self.today_template, 'r') as templ_file:
                    template = templ_file.read()
            except (IOError, OSError):
                self._error_pass(
                    "unable to read template file, using default")
                template = default_template
        try:
            with open(today_file, 'w') as t_file:
                t_file.write(template)
        except (IOError, OSError):
            pass
        else:
            self.refresh()
            success = True
        return success

    def _date_or_none(self, datestr):
        """Verify a date object or a date string in ISO format
        and return a date object or None.

        Args:
            timestr (str): a datetime formatted string.

        Returns:
            timeobj (date): a valid date object or None.

        """
        if isinstance(datestr, date):
            dateobj = datestr.astimezone(tz=self.ltz)
        else:
            try:
                dateobj = dtparser.parse(datestr).astimezone(tz=self.ltz)
                dateobj = dateobj.date()
            except (TypeError, ValueError, dtparser.ParserError):
                dateobj = None
        return dateobj

    def _default_config(self):
        """Create a default configuration directory and file if they
        do not already exist.
        """
        if not os.path.exists(self.config_file):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                with open(self.config_file, "w",
                          encoding="utf-8") as config_file:
                    config_file.write(self.dflt_config)
            except IOError:
                self._error_exit(
                    "Config file doesn't exist "
                    "and can't be created.")

    @staticmethod
    def _error_exit(errormsg):
        """Print an error message and exit with a status of 1

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')
        sys.exit(1)

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')

    def _generate_month_calendar(self, year, month, entries):
        """Generates a formatted monthly calendar with event
        days highlighted.

        Args:
            year (int): the calendar year.
            month (int): the calendar month.
            entries (dict): the events for a datetime range.

        Returns:
            cal_txt (obj): a formatted Text object.

        """
        calendar.setfirstweekday(self.first_weekday)
        months = list(calendar.month_name)

        cal_title_style = Style(color=self.color_calendar,
                                bold=self.color_bold)
        cal_days_style = Style(color=self.color_calendar,
                               underline=True)
        month_hdr = Text(f"{months[month]} {year}\n",
                         style=cal_title_style, justify='center')
        month_day_line = Text(calendar.weekheader(2),
                              style=cal_days_style)
        month_txt = Text("")
        for week in calendar.monthcalendar(year, month):
            week_txt = Text("")
            for day in week:
                if day == 0:
                    day_txt = "  "
                else:
                    highlight = False
                    for entry in entries:
                        if date(year, month, day) == entry['date']:
                            highlight = True
                    if highlight:
                        day_txt = Text(
                                f"{day:02d}",
                                style=self.style_calendar_hl)
                    else:
                        day_txt = Text(
                                f"{day:02d}",
                                style=self.style_calendar)
                if week.index(day) != week[:-1]:
                    week_txt = Text.assemble(week_txt, day_txt, " ")
                else:
                    week_txt = Text.assemble(week_txt, day_txt)
            month_txt = Text.assemble(month_txt, week_txt, "\n")
        cal_txt = Text.assemble(
            month_hdr,
            "\n",
            month_day_line,
            "\n",
            month_txt)
        return cal_txt

    def _handle_error(self, msg):
        """Reports an error message and conditionally handles error exit
        or notification.

        Args:
            msg (str):  the error message.

        """
        if self.interactive:
            self._error_pass(msg)
        else:
            self._error_exit(msg)

    def _parse_config(self):
        """Read and parse the configuration file."""
        config = configparser.ConfigParser()
        if os.path.isfile(self.config_file):
            try:
                config.read(self.config_file)
            except configparser.Error:
                self._error_exit("Error reading config file")

            if "main" in config:
                if config["main"].get("data_dir"):
                    self.data_dir = os.path.expandvars(
                        os.path.expanduser(
                            config["main"].get("data_dir")))

                self.file_ext = config["main"].get("file_ext")
                self.today_options = config["main"].get("today_options")

                if config["main"].get("today_template"):
                    self.today_template = os.path.expandvars(
                        os.path.expanduser(
                            config["main"].get("today_template")))

                if config["main"].get("first_weekday"):
                    try:
                        self.first_weekday = int(
                                config["main"].get("first_weekday"))
                    except ValueError:
                        self.first_weekday = DEFAULT_FIRST_WEEKDAY

                if config["main"].get("show_calendar_week"):
                    try:
                        self.show_calendar_week = (config["main"]
                                                   .getboolean(
                                                       "show_calendar_week",
                                                       True))
                    except ValueError:
                        self.show_calendar_week = True

                if config["main"].get("show_calendar_month"):
                    try:
                        self.show_calendar_month = (config["main"]
                                                    .getboolean(
                                                        "show_calendar_month",
                                                        True))
                    except ValueError:
                        self.show_calendar_month = True

                if config["main"].get("show_calendar_year"):
                    try:
                        self.show_calendar_year = (config["main"]
                                                   .getboolean(
                                                       "show_calendar_year",
                                                       True))
                    except ValueError:
                        self.show_calendar_year = True

            def _apply_colors():
                """Try to apply custom colors and catch exceptions for
                invalid color names.
                """
                try:
                    self.style_title = Style(
                        color=self.color_title,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_border = Style(
                        color=self.color_border)
                except ColorParseError:
                    pass
                try:
                    self.style_date = Style(
                        color=self.color_date)
                except ColorParseError:
                    pass
                try:
                    self.style_dateheader = Style(
                        color=self.color_dateheader,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_calendar = Style(
                        color=self.color_calendar)
                except ColorParseError:
                    pass
                try:
                    self.style_calendar_hl = Style(
                        color=self.color_calendar_hl,
                        bold=self.color_bold)
                except ColorParseError:
                    pass

            # apply default colors
            _apply_colors()

            if "colors" in config:
                # custom colors with fallback to defaults
                self.color_title = (
                    config["colors"].get(
                        "title", "bright_blue"))
                self.color_border = (
                    config["colors"].get(
                        "border", "white"))
                self.color_date = (
                    config["colors"].get(
                        "date", "green"))
                self.color_dateheader = (
                    config["colors"].get(
                        "dateheader", "blue"))
                self.color_calendar = (
                    config["colors"].get(
                        "calendar", "bright_cyan"))
                self.color_calendar_hl = (
                    config["colors"].get(
                        "calendar_hl", "yellow"))

                # color paging (disabled by default)
                self.color_pager = config["colors"].getboolean(
                    "color_pager", "False")

                # disable colors
                if bool(config["colors"].getboolean("disable_colors")):
                    self.color_title = "default"
                    self.color_border = "default"
                    self.color_date = "default"
                    self.color_dateheader = "default"
                    self.color_calendar = "default"
                    self.color_calendar_hl = "default"

                # disable bold
                if bool(config["colors"].getboolean("disable_bold")):
                    self.color_bold = False

                # try to apply requested custom colors
                _apply_colors()
        else:
            self._error_exit("Config file not found")

    def _parse_files(self):
        """ Read journal entry files from `data_dir` and parse event
        data into`events`.

        Returns:
            events (dict):    parsed data from each event file

        """
        temp_entries = {}

        with os.scandir(self.data_dir) as entries:
            for entry in entries:
                entrydt = None
                if self.file_ext:
                    if (entry.name.endswith(f".{self.file_ext}") and
                            entry.is_file()):
                        name = entry.name.replace(f".{self.file_ext}", '')
                        entrydt = self._date_or_none(name)
                else:
                    if entry.is_file():
                        name = entry.name
                        entrydt = self._date_or_none(name)
                if entrydt:
                    try:
                        with open(entry.path, "r",
                                  encoding="utf-8") as entry_file:
                            contents = entry_file.read()
                    except (OSError, IOError):
                        self._error_pass(
                            f"failure reading {entry.path} "
                            "- SKIPPING")
                    else:
                        data = {}
                        data['date'] = entrydt
                        data['path'] = entry.path
                        data['contents'] = contents
                        temp_entries[name] = data

        # sort the journal entries by date
        fifoentries = {}
        for entry in temp_entries:
            sort = temp_entries[entry].get('date')
            fifoentries[entry] = sort
        sortlist = sorted(fifoentries.items(), key=lambda x: x[1])
        sorted_entries = dict(sortlist)
        self.entries = {}
        for key in sorted_entries.keys():
            self.entries[key] = temp_entries[key]

    def _print_entries_list(
            self,
            entries,
            view,
            pager=False,
            weekstart=None,
            month=None,
            year=None,
            excerpt=False):
        """Print the formatted events list.

        Args:
            entries (list):   the list of events to be printed in a
            formatted manner.
            view (str):     the view to display (e.g., day, month, etc.)
            pager (bool):   whether or not to page output (default no).
            weekstart (obj): datetime object of the first day in the week.
            month (int):    the month for the current view.
            year (int):     the year for the current view.
            excerpt (bool): whether or not to include an excerpt (in the
        'excerpt' field, added by search()).

        """
        console = Console()
        title = f"Entries - {view}"
        # table
        entry_table = Table(
            title=title,
            title_style=self.style_title,
            title_justify="left",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            collapse_padding=False,
            min_width=30,
            padding=(0, 0, 0, 0))
        # single column
        entry_table.add_column("column1")
        if (view.endswith("week") and
                weekstart and
                self.show_calendar_week):
            day1 = weekstart
            day2 = weekstart + timedelta(days=1)
            day3 = weekstart + timedelta(days=2)
            day4 = weekstart + timedelta(days=3)
            day5 = weekstart + timedelta(days=4)
            day6 = weekstart + timedelta(days=5)
            day7 = weekstart + timedelta(days=6)
            week_table = Table(
                title=None,
                box=box.SQUARE,
                show_header=True,
                header_style=self.style_dateheader,
                border_style=self.style_border,
                show_lines=False,
                pad_edge=True,
                collapse_padding=False,
                padding=(0, 0, 0, 0))
            week_table.add_column(
                day1.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day2.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day3.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day4.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day5.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day6.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            week_table.add_column(
                day7.strftime("%a"),
                justify="center",
                no_wrap=True,
                style=self.style_date)
            daytxt = {}
            day = 1
            for weekday in [day1, day2, day3, day4, day5, day6, day7]:
                highlight = False
                for entry in entries:
                    if weekday == entry['date']:
                        highlight = True
                if highlight:
                    daytxt[day] = Text(
                            weekday.strftime("%m-%d"),
                            style=self.style_calendar_hl)
                else:
                    daytxt[day] = Text(
                            weekday.strftime("%m-%d"),
                            style=self.style_calendar)
                day += 1

            week_table.add_row(
                daytxt[1],
                daytxt[2],
                daytxt[3],
                daytxt[4],
                daytxt[5],
                daytxt[6],
                daytxt[7])
            entry_table.add_row(week_table)
            entry_table.add_row(" ")
        elif (view.endswith('month') and
                year and
                month and
                self.show_calendar_month):
            month_table = Table(
                title=None,
                box=box.SQUARE,
                show_header=False,
                border_style=self.style_border,
                show_lines=False,
                pad_edge=True,
                collapse_padding=False,
                padding=(1, 0, 0, 1))
            month_table.add_column("single")
            month_table.add_row(
                    self._generate_month_calendar(year, month, entries))
            entry_table.add_row(month_table)
            entry_table.add_row(" ")
        elif (view.endswith('year') and
                year and
                self.show_calendar_year):
            calendar.setfirstweekday(self.first_weekday)
            year_table = Table(
                title=None,
                box=box.SQUARE,
                show_header=False,
                border_style=self.style_border,
                show_lines=True,
                pad_edge=True,
                collapse_padding=False,
                padding=(1, 0, 0, 1))
            if console.width >= 95:
                # four-column calendar view
                year_table.add_column("one")
                year_table.add_column("two")
                year_table.add_column("three")
                year_table.add_column("four")
                year_table.add_row(
                    self._generate_month_calendar(year, 1, entries),
                    self._generate_month_calendar(year, 2, entries),
                    self._generate_month_calendar(year, 3, entries),
                    self._generate_month_calendar(year, 4, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 5, entries),
                    self._generate_month_calendar(year, 6, entries),
                    self._generate_month_calendar(year, 7, entries),
                    self._generate_month_calendar(year, 8, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 9, entries),
                    self._generate_month_calendar(year, 10, entries),
                    self._generate_month_calendar(year, 11, entries),
                    self._generate_month_calendar(year, 12, entries))
                entry_table.add_row(year_table)
                entry_table.add_row(" ")
            elif console.width >= 72:
                # three-column calendar view
                year_table.add_column("one")
                year_table.add_column("two")
                year_table.add_column("three")
                year_table.add_row(
                    self._generate_month_calendar(year, 1, entries),
                    self._generate_month_calendar(year, 2, entries),
                    self._generate_month_calendar(year, 3, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 4, entries),
                    self._generate_month_calendar(year, 5, entries),
                    self._generate_month_calendar(year, 6, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 7, entries),
                    self._generate_month_calendar(year, 8, entries),
                    self._generate_month_calendar(year, 9, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 10, entries),
                    self._generate_month_calendar(year, 11, entries),
                    self._generate_month_calendar(year, 12, entries))
                entry_table.add_row(year_table)
                entry_table.add_row(" ")
            else:
                # two-column calendar view
                year_table.add_column("one")
                year_table.add_column("two")
                year_table.add_row(
                    self._generate_month_calendar(year, 1, entries),
                    self._generate_month_calendar(year, 2, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 3, entries),
                    self._generate_month_calendar(year, 4, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 5, entries),
                    self._generate_month_calendar(year, 6, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 7, entries),
                    self._generate_month_calendar(year, 8, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 9, entries),
                    self._generate_month_calendar(year, 10, entries))
                year_table.add_row(
                    self._generate_month_calendar(year, 11, entries),
                    self._generate_month_calendar(year, 12, entries))
                entry_table.add_row(year_table)
                entry_table.add_row(" ")
        # event list
        if entries:
            for entry in entries:
                datetxt = Text(f" - {str(entry['date'])}")
                datetxt.stylize(self.style_date)
                entry_table.add_row(datetxt)
                if excerpt:
                    this_excerpt = entry.get('excerpt')
                    if this_excerpt:
                        excerpttxt = Padding(this_excerpt, (0, 0, 0, 4))
                        entry_table.add_row(excerpttxt)
        else:
            entry_table.add_row("None")
        # single-column layout
        layout = Table.grid()
        layout.add_column("single")
        layout.add_row("")
        layout.add_row(entry_table)

        # render the output with a pager if -p
        if pager:
            if self.color_pager:
                with console.pager(styles=True):
                    console.print(layout)
            else:
                with console.pager():
                    console.print(layout)
        else:
            console.print(layout)

    def _verify_data_dir(self):
        """Create the journal data directory if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except IOError:
                self._error_exit(
                    f"{self.data_dir} doesn't exist "
                    "and can't be created")
        elif not os.path.isdir(self.data_dir):
            self._error_exit(f"{self.data_dir} is not a directory")
        elif not os.access(self.data_dir,
                           os.R_OK | os.W_OK | os.X_OK):
            self._error_exit(
                "You don't have read/write/execute permissions to "
                f"{self.data_dir}")

    def delete(self, entry, force=False):
        """Delete a journal entry.

        Args:
            entry (str):    The journal entry to be deleted.

        """
        entry_data = self.entries.get(entry)
        if entry_data:
            if force:
                confirm = "yes"
            else:
                confirm = input(f"Delete '{entry}'? [yes/no]: ").lower()
            if confirm in ['yes', 'y']:
                filename = entry_data.get('path')
                if filename:
                    try:
                        os.remove(filename)
                    except OSError:
                        self._handle_error(f"failure deleting {filename}")
                    else:
                        print(f"Deleted entry: {entry}")
                else:
                    self._handle_error(f"failed to find file for {entry}")
            else:
                print("Cancelled.")
        else:
            self._handle_error(f"failed to find entry for {entry}")

    def edit_config(self):
        """Edit the config file (using $EDITOR) and then reload config."""
        if self.editor:
            try:
                subprocess.run(
                    [self.editor, self.config_file], check=True)
            except subprocess.SubprocessError:
                self._handle_error("failure editing config file")
            else:
                if self.interactive:
                    self._parse_config()
                    self.refresh()
        else:
            self._handle_error("$EDITOR is required and not set")

    def open(self, entry):
        """Opens a journal entry (using $EDITOR). If the entry is for
        'today' create the entry if it doesn't exist.

        Args:
            entry (str):    The journal entry to be edited.

        """
        is_today = False
        today = date.today()
        yesterday = today - timedelta(days=1)
        dateobj = self._date_or_none(entry)
        if dateobj == today:
            entry = 'today'
        if entry == 'today':
            is_today = True
            entry = str(today)
            if entry not in self.entries.keys():
                created = self._create_today()
                if not created:
                    self._handle_error(
                        "unable to create journal entry for today")
        elif entry == 'yesterday':
            entry = str(yesterday)
        else:
            if entry not in self.entries.keys():
                if dateobj:
                    print(f"Entry for {entry} doesn't exist.")
                    add_new = input(
                        "Would you like to create an entry for "
                        f"{entry}? [N/y]: ").lower()
                    if add_new in ['y', 'yes']:
                        created = self._create_entry(dateobj)
                        if not created:
                            msg = (
                                f"unable to create journal entry for {entry}")
                            if self.interactive:
                                self._error_pass(msg)
                                return
                            else:
                                self._error_exit(msg)
                    else:
                        msg = (f"Entry for {entry} not created.")
                        if self.interactive:
                            print(msg)
                            return
                        else:
                            print(msg)
                            sys.exit(0)
                else:
                    msg = f"'{entry}' is not a valid date"
                    if self.interactive:
                        self._error_pass(msg)
                        return
                    else:
                        self._error_exit(msg)

        entry_data = self.entries.get(entry)
        if entry_data:
            if self.editor:
                filename = entry_data.get('path')
                if filename:
                    if self.today_options and is_today:
                        editorcmd = (
                            f"{self.editor} {self.today_options} {filename}"
                        )
                    else:
                        editorcmd = f"{self.editor} {filename}"
                    try:
                        if is_today:
                            now = datetime.now(
                                    tz=self.ltz).strftime(" - %H:%M: ")
                            with open(filename, 'a') as entry_file:
                                entry_file.write(now)
                        subprocess.run(
                                editorcmd,
                                check=True,
                                shell=True)
                    except (IOError, OSError, subprocess.SubprocessError):
                        self._handle_error(f"failure opening file {filename}")
                else:
                    self._handle_error(f"failed to find file for {entry}")
            else:
                self._handle_error("$EDITOR is required and not set")
        else:
            self._handle_error(f"failed to find data for {entry}")

    def list(
            self,
            view,
            start=None,
            end=None,
            page=None):
        """Prints a list of journal entries within a view.

        Args:
            view (str):     the journal view (thisweek, lastweek,
        thismonth, lastmonth, thisyear, lastyear, or custom)
            start (str):    datetime-like string for start date.
            end (str):      datetime-like string for end date.

        """
        startstr = start
        endstr = end
        start = self._date_or_none(start)
        end = self._date_or_none(end)
        view = view.lower()
        cal = calendar.Calendar(firstweekday=self.first_weekday)
        today = date.today()
        today_wd = today.weekday()
        this_year = today.year
        last_year = this_year - 1
        this_month = today.month
        this_month_ld = calendar.monthrange(this_year, this_month)[1]
        last_month = this_month - 1
        if last_month == 0:
            last_month = 12
            lm_year = this_year - 1
        else:
            lm_year = this_year
        last_month_ld = calendar.monthrange(lm_year, last_month)[1]
        this_week_start = today - timedelta(
                days=list(cal.iterweekdays()).index(today_wd))
        this_week_end = this_week_start + timedelta(days=6)
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = last_week_start + timedelta(days=6)
        if view == "thisweek":
            selected_entries = []
            for entry in self.entries:
                data = self.entries[entry]
                if this_week_start <= data['date'] <= this_week_end:
                    selected_entries.append(data)
            self._print_entries_list(
                selected_entries, "this week", page, this_week_start)
        elif view == "lastweek":
            selected_entries = []
            for entry in self.entries:
                data = self.entries[entry]
                if last_week_start <= data['date'] <= last_week_end:
                    selected_entries.append(data)
            self._print_entries_list(
                    selected_entries, "last week", page, last_week_start)
        elif view == "thismonth":
            selected_entries = []
            this_month_start = date(this_year, this_month, 1)
            this_month_end = date(this_year, this_month, this_month_ld)
            for entry in self.entries:
                data = self.entries[entry]
                if this_month_start <= data['date'] <= this_month_end:
                    selected_entries.append(data)
            self._print_entries_list(
                    selected_entries,
                    "this month",
                    page,
                    month=this_month,
                    year=this_year)
        elif view == "lastmonth":
            selected_entries = []
            last_month_start = date(lm_year, last_month, 1)
            last_month_end = date(lm_year, last_month, last_month_ld)
            for entry in self.entries:
                data = self.entries[entry]
                if last_month_start <= data['date'] <= last_month_end:
                    selected_entries.append(data)
            self._print_entries_list(
                    selected_entries,
                    "last month",
                    page,
                    month=last_month,
                    year=lm_year)
        elif view == "thisyear":
            selected_entries = []
            this_year_start = date(this_year, 1, 1)
            this_year_end = date(this_year, 12, 31)
            for entry in self.entries:
                data = self.entries[entry]
                if this_year_start <= data['date'] <= this_year_end:
                    selected_entries.append(data)
            self._print_entries_list(
                    selected_entries,
                    "this year",
                    page,
                    year=this_year)
        elif view == "lastyear":
            selected_entries = []
            last_year_start = date(last_year, 1, 1)
            last_year_end = date(last_year, 12, 31)
            for entry in self.entries:
                data = self.entries[entry]
                if last_year_start <= data['date'] <= last_year_end:
                    selected_entries.append(data)
            self._print_entries_list(
                    selected_entries,
                    "last year",
                    page,
                    year=last_year)
        elif view == "custom" and start and end:
            selected_entries = []
            for entry in self.entries:
                data = self.entries[entry]
                if start <= data['date'] <= end:
                    selected_entries.append(data)
            self._print_entries_list(
                    selected_entries,
                    f"custom\n[{startstr} - {endstr}]",
                    page)
        else:
            self._handle_error(
                "invalid view name or custom date/time range")

    def refresh(self):
        """Public method to refresh data."""
        self._parse_files()

    def search(self, term, pager=False):
        """Perform a search for entries that match a given term and
        print the results in formatted text.

        Args:
            term (str):     the text for which to search. this can be a
        regex in the form '/{term}/'.
            pager (bool):   whether to page output.

        """
        # check for regular expression
        if term.startswith('/') and term.endswith('/'):
            test_term = term[1:-2]
            try:
                r_term = re.compile(test_term)
            except re.error:
                regex = False
                self._error_pass(
                    "not a valid regex, falling back to regular search")
            else:
                regex = True
                term = r_term
        else:
            regex = False
        if term:
            result_events = []
            for entry in self.entries:
                data = self.entries[entry]
                contents = data['contents'].split('\n')
                matches = []
                for line in contents:
                    if regex:
                        r_match = re.search(term, line)
                        if r_match:
                            matches.append(line.strip())
                    else:
                        if term.lower() in line.lower():
                            matches.append(line.strip())
                if matches:
                    data['excerpt'] = '\n'.join(matches)
                    result_events.append(data)
            self._print_entries_list(
                    result_events,
                    'search results',
                    pager,
                    excerpt=True)


class FSHandler(FileSystemEventHandler):
    """Handler to watch for file changes and refresh data from files.

    Attributes:
        shell (obj):    the calling shell object.

    """
    def __init__(self, shell):
        """Initializes an FSHandler() object."""
        self.shell = shell

    def on_any_event(self, event):
        """Refresh data in memory on data file changes.
        Args:
            event (obj):    file system event.
        """
        if event.event_type in [
                'created', 'modified', 'deleted', 'moved']:
            self.shell.do_refresh("silent")


class EntriesShell(Cmd):
    """Provides methods for interactive shell use.

    Attributes:
        entries (obj):     an instance of Entries().

    """
    def __init__(
            self,
            entries,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes an EntriesShell() object."""
        super().__init__()
        self.entries = entries

        # start watchdog for data_dir changes
        # and perform refresh() on changes
        observer = Observer()
        handler = FSHandler(self)
        observer.schedule(
                handler,
                self.entries.data_dir,
                recursive=True)
        observer.start()

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )
        self.do_clear(None)

        print(
            f"{APP_NAME} {APP_VERS}\n\n"
            f"Enter command (or 'help')\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args == "quit":
            self.do_exit("")
        elif args == "lsc":
            self.do_list("custom")
        elif args == "lsc |":
            self.do_list("custom |")
        elif args == "lstw":
            self.do_list("thisweek")
        elif args == "lstw |":
            self.do_list("thisweek |")
        elif args == "lspw":
            self.do_list("lastweek")
        elif args == "lspw |":
            self.do_list("lastweek |")
        elif args == "lstm":
            self.do_list("thismonth")
        elif args == "lstm |":
            self.do_list("thismonth |")
        elif args == "lspm":
            self.do_list("lastmonth")
        elif args == "lspm |":
            self.do_list("lastmonth |")
        elif args == "lsty":
            self.do_list("thisyear")
        elif args == "lsty |":
            self.do_list("thisyear |")
        elif args == "lspy":
            self.do_list("lastyear")
        elif args == "lspy |":
            self.do_list("lastyear |")
        elif args.startswith("ls"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_list(newargs[1])
            else:
                self.do_list("")
        elif args.startswith("rm"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_delete(newargs[1])
            else:
                self.do_delete("")
        elif args == "otd":
            self.do_open("today")
        elif args == "opd":
            self.do_open("yesterday")
        else:
            print("\nNo such command. See 'help'.\n")

    def emptyline(self):
        """Ignore empty line entry."""

    def _set_prompt(self):
        """Set the prompt string."""
        if self.entries.color_bold:
            self.prompt = "\033[1mjournal\033[0m> "
        else:
            self.prompt = "journal> "

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_config(self, args):
        """Edit the config file and reload the configuration.

        Args:
            args (str): the command arguments, ignored.

        """
        self.entries.edit_config()

    def do_delete(self, args):
        """Delete an entry.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.entries.delete(str(commands[0]).lower())
        else:
            self.help_delete()

    @staticmethod
    def do_exit(args):
        """Exit the entries shell.

        Args:
            args (str): the command arguments, ignored.

        """
        sys.exit(0)

    def do_list(self, args):
        """Output a list of entries.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            view = str(commands[0]).lower()
            page = False
            if len(commands) > 1:
                if str(commands[1]) == "|":
                    page = True
            if view == "custom":
                try:
                    start = input("Date/time range start: ") or None
                    end = input("Date/time range end: ") or None
                    if not start or not end:
                        print(
                            "The 'custom' view requires both a 'start' "
                            "and 'end' date."
                        )
                except KeyboardInterrupt:
                    print("\nCancelled.")
                else:
                    self.entries.list(
                        view,
                        start=start,
                        end=end,
                        page=page)
            else:
                self.entries.list(view, page=page)
        else:
            self.help_list()

    def do_open(self, args):
        """Open an entry via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.entries.open(str(commands[0]).lower())
        else:
            self.help_open()

    def do_refresh(self, args):
        """Refresh entry information if files changed on disk.

        Args:
            args (str): the command arguments, ignored.

        """
        self.entries.refresh()
        if args != 'silent':
            print("Data refreshed.")

    def do_search(self, args):
        """Search for entries that meet certain criteria.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            term = str(args).strip()
            if term.endswith('|'):
                term = term[:-1].strip()
                page = True
            else:
                page = False
            self.entries.search(term, page)
        else:
            self.help_search()

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_config():
        """Output help for 'config' command."""
        print(
            '\nconfig:\n'
            '    Edit the config file with $EDITOR and then reload '
            'the configuration and refresh data files.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (rm) <alias>:\n'
            '    Delete an entry file.\n'
        )

    @staticmethod
    def help_exit():
        """Output help for 'exit' command."""
        print(
            '\nexit:\n'
            '    Exit the entries shell.\n'
        )

    @staticmethod
    def help_list():
        """Output help for 'list' command."""
        print(
            '\nlist (ls) <view> [|]:\n'
            '    List entries using one of the views \'thisweek\', '
            '\'lastweek\', \'thismonth\', \'lastmonth\', \'thisyear\', '
            '\'lastyear\', or \'custom\'. Add \'|\' as a second '
            'argument to page the output.\n\n'
            '    The following command shortcuts are available:\n\n'
            '      lstw : list thisweek\n'
            '      lspw : list lastweek\n'
            '      lstm : list thismonth\n'
            '      lspm : list lastmonth\n'
            '      lsty : list thisyear\n'
            '      lspy : list lastyear\n'
            '      lsc  : list custom\n'
        )

    @staticmethod
    def help_open():
        """Output help for 'open' command."""
        print(
            '\nopen <date>:\n'
            '    Open an entry file with $EDITOR.\n\n'
            '    The following command shortcuts are available:\n\n'
            '      otd : open today\n'
            '      opd : open yesterday\n'
        )

    @staticmethod
    def help_refresh():
        """Output help for 'refresh' command."""
        print(
            '\nrefresh:\n'
            '    Refresh the entry information from files on disk. '
            'This is useful if changes were made to files outside of '
            'the program shell (e.g. sync\'d from another computer).\n'
        )

    @staticmethod
    def help_search():
        """Output help for 'search' command."""
        print(
            '\nsearch <term> [|]:\n'
            '    Search for an entry or entries that meet some specified '
            'criteria. Add \'|\' as a second argument to page the '
            'output.\n'
        )


def parse_args():
    """Parse command line arguments.

    Returns:
        args (dict):    the command line arguments provided.

    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description='Terminal-based journal management for nerds.')
    parser._positionals.title = 'commands'
    parser.set_defaults(command=None)
    subparsers = parser.add_subparsers(
        metavar=f'(for more help: {APP_NAME} <command> -h)')
    pager = subparsers.add_parser('pager', add_help=False)
    pager.add_argument(
        '-p',
        '--page',
        dest='page',
        action='store_true',
        help="page output")
    config = subparsers.add_parser(
        'config',
        help='edit configuration file')
    config.set_defaults(command='config')
    delete = subparsers.add_parser(
        'delete',
        aliases=['rm'],
        help='delete an entry file')
    delete.add_argument(
        'date',
        help='journal date')
    delete.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="delete without confirmation")
    delete.set_defaults(command='delete')
    listcmd = subparsers.add_parser(
        'list',
        aliases=['ls'],
        parents=[pager],
        help='list entries')
    listcmd.add_argument(
        'view',
        help='list view (thisweek, lastweek, etc.)')
    listcmd.add_argument(
        '--start',
        dest='cstart',
        help='start date/time for custom range')
    listcmd.add_argument(
        '--end',
        dest='cend',
        help='end date/time for custom range')
    listcmd.set_defaults(command='list')
    # list shortcuts
    lsc = subparsers.add_parser('lsc', parents=[pager])
    lsc.add_argument(
        '--start',
        dest='cstart',
        help='start date/time for custom range')
    lsc.add_argument(
        '--end',
        dest='cend',
        help='end date/time for custom range')
    lsc.set_defaults(command='lsc')
    lstw = subparsers.add_parser('lstw', parents=[pager])
    lstw.set_defaults(command='lstw')
    lspw = subparsers.add_parser('lspw', parents=[pager])
    lspw.set_defaults(command='lspw')
    lstm = subparsers.add_parser('lstm', parents=[pager])
    lstm.set_defaults(command='lstm')
    lspm = subparsers.add_parser('lspm', parents=[pager])
    lspm.set_defaults(command='lspm')
    lsty = subparsers.add_parser('lsty', parents=[pager])
    lsty.set_defaults(command='lsty')
    lspy = subparsers.add_parser('lspy', parents=[pager])
    lspy.set_defaults(command='lspy')
    opencmd = subparsers.add_parser(
        'open',
        help='open a journal entry')
    opencmd.add_argument(
        'date',
        help='entry date, "today", or "yesterday"')
    opencmd.set_defaults(command='open')
    # open shortcuts
    otd = subparsers.add_parser('otd')
    otd.set_defaults(command='otd')
    opd = subparsers.add_parser('opd')
    opd.set_defaults(command='opd')
    search = subparsers.add_parser(
        'search',
        parents=[pager],
        help='search entries')
    search.add_argument(
        'term',
        help='search term')
    search.set_defaults(command='search')
    shell = subparsers.add_parser(
        'shell',
        help='interactive shell')
    shell.set_defaults(command='shell')
    version = subparsers.add_parser(
        'version',
        help='show version info')
    version.set_defaults(command='version')
    parser.add_argument(
        '-c',
        '--config',
        dest='config',
        metavar='<file>',
        help='config file')
    args = parser.parse_args()
    return parser, args


def main():
    """Entry point. Parses arguments, creates Entries() object, calls
    requested method and parameters.
    """
    if os.environ.get("XDG_CONFIG_HOME"):
        config_file = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_CONFIG_HOME"])), APP_NAME, "config")
    else:
        config_file = os.path.expandvars(
            os.path.expanduser(DEFAULT_CONFIG_FILE))

    if os.environ.get("XDG_DATA_HOME"):
        data_dir = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_DATA_HOME"])), APP_NAME)
    else:
        data_dir = os.path.expandvars(
            os.path.expanduser(DEFAULT_DATA_DIR))

    parser, args = parse_args()

    if args.config:
        config_file = os.path.expandvars(
            os.path.expanduser(args.config))

    entries = Entries(
        config_file,
        data_dir,
        DEFAULT_CONFIG)

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)
    elif args.command == "config":
        entries.edit_config()
    elif args.command == "list":
        entries.list(args.view,
                     start=args.cstart,
                     end=args.cend,
                     page=args.page)
    elif args.command == "lstw":
        entries.list('thisweek', page=args.page)
    elif args.command == "lspw":
        entries.list('lastweek', page=args.page)
    elif args.command == "lstm":
        entries.list('thismonth', page=args.page)
    elif args.command == "lspm":
        entries.list('lastmonth', page=args.page)
    elif args.command == "lsty":
        entries.list('thisyear', page=args.page)
    elif args.command == "lspy":
        entries.list('lastyear', page=args.page)
    elif args.command == "lsc":
        entries.list('custom',
                     start=args.cstart,
                     end=args.cend,
                     page=args.page)
    elif args.command == "open":
        entries.open(args.date)
    elif args.command == "otd":
        entries.open('today')
    elif args.command == "opd":
        entries.open('yesterday')
    elif args.command == "delete":
        entries.delete(args.date, args.force)
    elif args.command == "search":
        entries.search(args.term, args.page)
    elif args.command == "shell":
        entries.interactive = True
        shell = EntriesShell(entries)
        shell.cmdloop()
    elif args.command == "version":
        print(f"{APP_NAME} {APP_VERS}")
        print(APP_COPYRIGHT)
        print(APP_LICENSE)
    else:
        sys.exit(1)


# entry point
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
