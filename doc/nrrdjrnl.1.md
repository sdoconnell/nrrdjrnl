---
title: NRRDJRNL
section: 1
header: User Manual
footer: nrrdjrnl 0.0.2
date: January 3, 2022
---
# NAME
nrrdjrnl - Terminal-based journal management for nerds.

# SYNOPSIS
**nrrdjrnl** *command* [*OPTION*]...

# DESCRIPTION
**nrrdjrnl** is a terminal-based journal management program with search and list options, and data stored in local text files. It can be run in either of two modes: command-line or interactive shell.

# OPTIONS
**-h**, **--help**
: Display help information.

**-c**, **--config** *file*
: Use a non-default configuration file.

# COMMANDS
**nrrdjrnl** provides the following commands.

**config**
: Edit the **nrrdjrnl** configuration file.

**delete (rm)** *alias* [*OPTION*]
: Delete a journal entry and entry file. The user will be prompted for confirmation.

    *OPTIONS*

    **-f**, **--force**
    : Force deletion, do not prompt for confirmation.

**list (ls)** *view* [*OPTION*]...
: List journal entries matching one of the following views:

    - *thisweek* (*lstw*) : All events for this week.
    - *lastweek* (*lspw*) : All events for last week.
    - *thismonth* (*lstm*) : All events for this month.
    - *lastmonth* (*lspm*) : All events for last month.
    - *thisyear* (*lsty*) : All events for this year.
    - *lastyear* (*lspy*) : All events for last year.
    - *custom* (*lsc*) : All events in a date range between **--start** and **--end**.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.

    **--start** *YYYY-MM-DD*
    : The start date for a custom range.

    **--end** *YYYY-MM-DD*
    : The end date for a custom range.

**open** *today*|*yesterday*|*DATE*
: Open a journal entry. If a journal entry doesn't exist for 'today' it will be automatically created. If a journal entry for another date doesn't exist, the user will be prompted to create a new file. *otd* is the shortcut for *open today*, *opd* is the shortcut for *open yesterday*.

**search** *searchterm* [*OPTION*]
: Search for one or more journal entries and output a tabular list (same format as **list**) with an excerpt of matching text. Optionally, a regular expression may be used by enclosing the term in "/" (i.e., "/\<regex to search for\>/").

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**shell**
: Launch the **nrrdjrnl** interactive shell.

**version**
: Show the application version information.

# NOTES

## Paging
Output from **list** and **search** can get long and run past your terminal buffer. You may use the **-p** or **--page** option in conjunction with **search** or **list** to page output.

# FILES
**~/.config/nrrdjrnl/config**
: Default configuration file

**~/.local/share/nrrdjrnl**
: Default data directory

# AUTHORS
Written by Sean O'Connell <https://sdoconnell.net>.

# BUGS
Submit bug reports at: <https://github.com/sdoconnell/nrrdjrnl/issues>

# SEE ALSO
Further documentation and sources at: <https://github.com/sdoconnell/nrrdjrnl>
