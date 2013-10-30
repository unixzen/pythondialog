#! /usr/bin/env python
# -*- coding: utf-8 -*-

# demo.py --- Demonstration program and cheap test suite for pythondialog
#
# Copyright (C) 2002-2010, 2013  Florent Rougon
# Copyright (C) 2000  Robb Shecter, Sultanbek Tezadov
#
# This program is in the public domain.

"""Demonstration program for pythondialog.

This is a program demonstrating most of the possibilities offered by
the pythondialog module (which is itself a Python interface to the
well-known dialog utility, or any other program compatible with
dialog).

Executive summary
-----------------

If you are looking for a very simple example of pythondialog usage,
short and straightforward, please refer to simple_example.py. The
file you are now reading serves more as a demonstration of what can
be done with pythondialog and as a cheap test suite than as a first
time tutorial. However, it can also be used to learn how to invoke
the various widgets. The following paragraphs explain what you should
keep in mind if you read it for this purpose.


Most of the code in the MyApp class (which defines the actual
contents of the demo) relies on a class called MyDialog implemented
here that:

  1. wraps all widget-producing calls in a way that automatically
     spawns a "confirm quit" dialog box if the user presses the
     Escape key or chooses the Cancel button, and then redisplays the
     original widget if the user doesn't actually want to quit;

  2. provides a few additional dialog-related methods and convenience
     wrappers.

The handling in (1) is completely automatic, implemented with
MyDialog.__getattr__() returning decorated versions of the
widget-producing methods of dialog.Dialog. Therefore, most of the
demo can be read as if the module-level 'd' attribute were a
dialog.Dialog instance whereas it is actually a MyDialog instance.
The only meaningful difference is that MyDialog.<widget>() will never
return a CANCEL or ESC code (attributes of 'd', or more generally of
dialog.Dialog). The reason is that these return codes are
automatically handled by the MyDialog.__getattr__() machinery to
display the "confirm quit" dialog box.

In some cases (e.g., fselect_demo()), I wanted the "Cancel" button to
perform a specific action instead of spawning the "confirm quit"
dialog box. To achieve this, the widget is invoked using
dialog.Dialog.<widget> instead of MyDialog.<widget>, and the return
code is handled in a semi-manual way. A prominent feature that needs
such special-casing is the yesno widget, because the "No" button
corresponds to the CANCEL exit code, which in general must not be
interpreted as an attempt to quit the program!

To sum it up, you can read most of the code in the MyApp class (which
defines the actual contents of the demo) as if 'd' were a
dialog.Dialog instance. Just keep in mind that there is a little
magic behind the scenes that automatically handles the CANCEL and ESC
Dialog exit codes, which wouldn't be the case if 'd' were a
dialog.Dialog instance. For a first introduction to pythondialog with
simple stuff and absolutely no magic, please have a look at
simple_example.py.

"""


from __future__ import division
from __future__ import with_statement, unicode_literals, print_function
import sys, os, locale, stat, time, getopt, subprocess, traceback, textwrap
import pprint
import dialog
from dialog import DialogBackendVersion
from io import open
import atexit

progname = os.path.basename(sys.argv[0])
progversion = "0.8-py2"
version_blurb = """Demonstration program and cheap test suite for pythondialog.

Copyright (C) 2002-2010  Florent Rougon
Copyright (C) 2000  Robb Shecter, Sultanbek Tezadov

This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE."""

default_debug_filename = "pythondialog.debug"

usage = """Usage: {progname} [option ...]
Demonstration program and cheap test suite for pythondialog.

Options:
  -t, --test-suite             test all widgets; implies --fast
  -f, --fast                   fast mode (e.g., makes the gauge demo run faster)
      --debug                  enable logging of all dialog command lines
      --debug-file=FILE        where to write debug information (default:
                               {debug_file} in the current directory)
      --help                   display this message and exit
      --version                output version information and exit""".format(
    progname=progname, debug_file=default_debug_filename)

# Global parameters

# Set two global variables u_stdout and u_stderr referencing text streams,
# similar to sys.stdout and sys.stderr in Python 3.
for stream_name in ("stdout", "stderr"):
    _bstream = getattr(sys, stream_name)

    if hasattr(_bstream, b"encoding") and getattr(_bstream, b"encoding"):
        _encoding = getattr(_bstream, b"encoding")
    else:
        _encoding = locale.getpreferredencoding()

    _tstream = open(_bstream.fileno(), "w", encoding=_encoding, closefd=False)
    globals()["u_" + stream_name] = _tstream
    # Important, especially when the stream is not connected to a tty, for
    # instance when piping the output or redirecting it to a file. Indeed,
    # '_tstream' is fully buffered in such a case.
    atexit.register(lambda stream: stream.close(), _tstream)

    del _encoding, _bstream, _tstream

params = {}

# We'll use a module-level attribute 'd' ("global") to store the MyDialog
# instance that is used throughout the demo. This object could alternatively be
# passed to the MyApp constructor and stored there as a class or instance
# attribute. However, for the sake of readability, we'll simply use a global
# (d.msgbox(...) versus self.d.msgbox(...), etc.).
d = None

tw = textwrap.TextWrapper(width=78, break_long_words=False,
                          break_on_hyphens=True)
from textwrap import dedent

try:
    from textwrap import indent
except ImportError:
    def indent(text, prefix, predicate=None):
        l = []

        for line in text.splitlines(True):
            if (callable(predicate) and predicate(line)) \
                    or (not callable(predicate) and predicate) \
                    or (predicate is None and line.strip()):
                line = prefix + line
            l.append(line)

        return ''.join(l)


class MyDialog(object):
    """Wrapper class for dialog.Dialog.

    This class behaves similarly to dialog.Dialog. The differences
    are that:

      1. MyDialog wraps all widget-producing methods in a way that
         automatically spawns a "confirm quit" dialog box if the user
         presses the Escape key or chooses the Cancel button, and
         then redisplays the original widget if the user doesn't
         actually want to quit.

      2. MyDialog provides a few additional dialog-related methods
         and convenience wrappers.

    Please refer to the module docstring and to the particular
    methods for more details.

    """
    def __init__(self, Dialog_instance):
        self.dlg = Dialog_instance

    def check_exit_request(self, code, ignore_Cancel=False):
        if code == self.CANCEL and ignore_Cancel:
            # Ignore the Cancel button, i.e., don't interpret it as an exit
            # request; instead, let the caller handle CANCEL himself.
            return True

        if code in (self.CANCEL, self.ESC):
            button_name = { self.CANCEL: "Cancel",
                            self.ESC: "Escape" }
            msg = "You pressed {0} in the last dialog box. Do you want " \
                "to exit this demo?".format(button_name[code])
            # 'self.dlg' instead of 'self' here, because we want to use the
            # original yesno() method from the Dialog class instead of the
            # decorated method returned by self.__getattr__().
            if self.dlg.yesno(msg) == self.OK:
                sys.exit(0)
            else:               # "No" button chosen, or ESC pressed
                return False    # in the "confirm quit" dialog
        else:
            return True

    def widget_loop(self, method):
        """Decorator to handle eventual exit requests from a Dialog widget.

        method -- a dialog.Dialog method that returns either a Dialog
                  exit code, or a sequence whose first element is a
                  Dialog exit code (cf. the docstring of the Dialog
                  class in dialog.py)

        Return a wrapper function that behaves exactly like 'method',
        except for the following point:

          If the Dialog exit code obtained from 'method' is CANCEL or
          ESC (attributes of dialog.Dialog), a "confirm quit" dialog
          is spawned; depending on the user choice, either the
          program exits or 'method' is called again, with the same
          arguments and same handling of the exit status. In other
          words, the wrapper function builds a loop around 'method'.

        The above condition on 'method' is satisfied for all
        dialog.Dialog widget-producing methods. More formally, these
        are the methods defined with the @widget decorator in
        dialog.py, i.e., that have an "is_widget" attribute set to
        True.

        """
        # One might want to use @functools.wraps here, but since the wrapper
        # function is very likely to be used only once and then
        # garbage-collected, this would uselessly add a little overhead inside
        # __getattr__(), where widget_loop() is called.
        def wrapper(*args, **kwargs):
            while True:
                res = method(*args, **kwargs)

                if hasattr(method, "retval_is_code") \
                        and getattr(method, "retval_is_code"):
                    code = res
                else:
                    code = res[0]

                if self.check_exit_request(code):
                    break
            return res

        return wrapper

    def __getattr__(self, name):
        # This is where the "magic" of this class originates from.
        # Please refer to the module and self.widget_loop()
        # docstrings if you want to understand the why and the how.
        obj = getattr(self.dlg, name)
        if hasattr(obj, "is_widget") and getattr(obj, "is_widget"):
            return self.widget_loop(obj)
        else:
            return obj

    def clear_screen(self):
        # This program comes with ncurses
        program = "clear"

        try:
            p = subprocess.Popen([program], shell=False, stdout=None,
                                 stderr=None, close_fds=True)
            retcode = p.wait()
        except os.error, e:
            self.msgbox("Unable to execute program '%s': %s." % (program,
                                                              e.strerror),
                     title="Error")
            return False

        if retcode > 0:
            msg = "Program %s returned exit status %d." % (program, retcode)
        elif retcode < 0:
            msg = "Program %s was terminated by signal %d." % (program, -retcode)
        else:
            return True

        self.msgbox(msg)
        return False

    def _Yesno(self, *args, **kwargs):
        """Convenience wrapper around dialog.Dialog.yesno().

        Return the same exit code as would return
        dialog.Dialog.yesno(), except for ESC which is handled as in
        the rest of the demo, i.e. make it spawn the "confirm quit"
        dialog.

        """
        # self.yesno() automatically spawns the "confirm quit" dialog if ESC or
        # the "No" button is pressed, because of self.__getattr__(). Therefore,
        # we have to use self.dlg.yesno() here and call
        # self.check_exit_request() manually.
        while True:
            code = self.dlg.yesno(*args, **kwargs)
            # If code == self.CANCEL, it means the "No" button was chosen;
            # don't interpret this as a wish to quit the program!
            if self.check_exit_request(code, ignore_Cancel=True):
                break

        return code

    def Yesno(self, *args, **kwargs):
        """Convenience wrapper around dialog.Dialog.yesno().

        Return True if "Yes" was chosen, False if "No" was chosen,
        and handle ESC as in the rest of the demo, i.e. make it spawn
        the "confirm quit" dialog.

        """
        return self._Yesno(*args, **kwargs) == self.dlg.OK

    def Yesnohelp(self, *args, **kwargs):
        """Convenience wrapper around dialog.Dialog.yesno().

        Return "yes", "no", "extra" or "help" depending on the button
        that was pressed to close the dialog. ESC is handled as in
        the rest of the demo, i.e. it spawns the "confirm quit"
        dialog.

        """
        kwargs["help_button"] = True
        code = self._Yesno(*args, **kwargs)
        d = { self.dlg.OK:     "yes",
              self.dlg.CANCEL: "no",
              self.dlg.EXTRA:  "extra",
              self.dlg.HELP:   "help" }

        return d[code]


# Dummy context manager to make sure the debug file is closed on exit, be it
# normal or abnormal, and to avoid having two code paths, one for normal mode
# and one for debug mode.
class DummyContextManager(object):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class MyApp(object):
    def __init__(self):
        # The MyDialog instance 'd' could be passed via the constructor and
        # stored here as a class or instance attribute. However, for the sake
        # of readability, we'll simply use a module-level attribute ("global")
        # (d.msgbox(...) versus self.d.msgbox(...), etc.).
        global d
        # If you want to use Xdialog (pathnames are also OK for the 'dialog'
        # argument), you can use:
        #   dialog.Dialog(dialog="Xdialog", compat="Xdialog")
        self.Dialog_instance = dialog.Dialog(dialog="dialog")
        # See the module docstring at the top of the file to understand the
        # purpose of MyDialog.
        d = MyDialog(self.Dialog_instance)
        backtitle = "pythondialog demo"
        d.set_background_title(backtitle)
        # These variables take the background title into account
        self.max_lines, self.max_cols = d.maxsize(backtitle=backtitle)
        self.demo_context = self.setup_debug()
        # Warn if the terminal is smaller than this size
        self.min_rows, self.min_cols = 24, 80
        self.term_rows, self.term_cols, self.backend_version = \
            self.get_term_size_and_backend_version()

    def setup_debug(self):
        if params["debug"]:
            debug_file = open(params["debug_filename"], "w")
            d.setup_debug(True, file=debug_file)
            return debug_file
        else:
            return DummyContextManager()

    def get_term_size_and_backend_version(self):
        # Avoid running '<backend> --print-version' every time we need the
        # version
        backend_version = d.cached_backend_version
        if not backend_version:
            print(tw.fill(
                  "Unable to retrieve the version of the dialog-like backend. "
                  "Not running cdialog?") + "\nPress Enter to continue.",
                  file=u_stderr)
            raw_input()

        term_rows, term_cols = d.maxsize(use_persistent_args=False)
        if term_rows < self.min_rows or term_cols < self.min_cols:
            print(tw.fill(dedent("""\
             Your terminal has less than {0} rows or less than {1} columns;
             you may experience problems with the demo. You have been warned."""
                                 .format(self.min_rows, self.min_cols)))
                  + "\nPress Enter to continue.", file=u_stdout)
            raw_input()

        return (term_rows, term_cols, backend_version)

    def run(self):
        with self.demo_context:
            if params["testsuite_mode"]:
                # Show the additional widgets before the "normal demo", so that
                # I can test new widgets quickly and simply hit Ctrl-C once
                # they've been shown.
                self.additional_widgets()

            # "Normal" demo
            self.demo()

    def demo(self):
        d.msgbox("""\
Hello, and welcome to the pythondialog {pydlg_version} demonstration program.

You can scroll through this dialog box with the Page Up and Page Down keys. \
Please note that some of the dialogs will not work, and cause the demo to \
stop, if your terminal is too small. The recommended size is (at least) \
{min_rows} rows by {min_cols} columns.

This script is being run by a Python interpreter identified as follows:

{py_version}

The dialog-like program displaying this message box reports version \
{backend_version} and a terminal size of {rows} rows by {cols} columns."""
                 .format(
                pydlg_version=dialog.__version__,
                backend_version=self.backend_version,
                py_version=indent(sys.version, "  "),
                rows=self.term_rows, cols=self.term_cols,
                min_rows=self.min_rows, min_cols=self.min_cols),
                 width=60, height=17)

        self.progressbox_demo_with_file_descriptor()
        self.infobox_demo()
        self.gauge_demo()
        answer = self.yesno_demo(with_help=True)
        self.msgbox_demo(answer)
        self.textbox_demo()
        name = self.inputbox_demo_with_help()
        size, weight, city, state, country, last_will1, last_will2, \
            last_will3, last_will4, secret_code = self.mixedform_demo()
        self.form_demo_with_help()
        favorite_day = self.menu_demo(name, city, state, country, size, weight,
                                      secret_code, last_will1, last_will2,
                                      last_will3, last_will4)

        if self.dialog_version_check("1.2-20130902",
                                     "the menu demo with help facilities",
                                     explain=True):
            self.menu_demo_with_help()

        toppings = self.checklist_demo()
        if self.dialog_version_check("1.2-20130902",
                                     "the checklist demo with help facilities",
                                     explain=True):
            self.checklist_demo_with_help()

        sandwich = self.radiolist_demo()

        if self.dialog_version_check("1.2", "the rangebox demo", explain=True):
            nb_engineers = self.rangebox_demo()
        else:
            nb_engineers = None

        if self.dialog_version_check("1.2", "the buildlist demo", explain=True):
            desert_island_stuff = self.buildlist_demo()
        else:
            desert_island_stuff = None

        if self.dialog_version_check("1.2-20130902",
                                     "the buildlist demo with help facilities",
                                     explain=True):
            self.buildlist_demo_with_help()

        date = self.calendar_demo_with_help()
        time_ = self.timebox_demo()

        password = self.passwordbox_demo()
        self.scrollbox_demo(name, favorite_day, toppings, sandwich,
                            nb_engineers, desert_island_stuff, date, time_,
                            password)

        if self.dialog_version_check("1.2", "the treeview demo", explain=True):
            if self.dialog_version_check("1.2-20130902"):
                self.treeview_demo_with_help()
            else:
                self.treeview_demo()

        self.mixedgauge_demo()
        self.editbox_demo("/etc/passwd")
        self.inputmenu_demo()
        d.msgbox("""\
Haha. You thought it was over. Wrong. Even more fun is to come!

Now, please select a file you would like to see growing (or not...).""",
                 width=75)

        # Looks nicer if the screen is not completely filled by the widget,
        # hence the -1.
        self.tailbox_demo(height=self.max_lines-1,
                          width=self.max_cols)

        directory = self.dselect_demo()

        timeout = 2 if params["fast_mode"] else 20
        self.pause_demo(timeout)

        d.clear_screen()
        if not params["fast_mode"]:
            # Rest assured, this is not necessary in any way: it is only a
            # psychological trick to try to give the impression of a reboot
            # (cf. pause_demo(); would be even nicer with a "visual bell")...
            time.sleep(1)

    def additional_widgets(self):
        # Requires a careful choice of the file to be of any interest
        self.progressbox_demo_with_filepath()
        # This can be confusing without any pause if the user specified a
        # regular file.
        time.sleep(1 if params["fast_mode"] else 2)

        # programbox_demo would be fine right after
        # progressbox_demo_with_file_descriptor in demo(), but there is a
        # little bug in dialog 1.2-20130902 that makes the first two lines
        # disappear too early. Until the fix is widely deployed, it is probably
        # best to keep programbox_demo out of the main demo.
        if self.dialog_version_check("1.1", "the programbox demo", explain=True):
            self.programbox_demo()
        # Almost identical to mixedform (mixedform being more powerful). Also,
        # there is now form_demo_with_help() which uses the form widget.
        self.form_demo()
        # Almost identical to passwordbox
        self.passwordform_demo()

    def dialog_version_check(self, version_string, feature="", **_3to2kwargs):
        if 'explain' in _3to2kwargs: explain = _3to2kwargs['explain']; del _3to2kwargs['explain']
        else: explain = False
        if 'start' in _3to2kwargs: start = _3to2kwargs['start']; del _3to2kwargs['start']
        else: start = ""

        if d.compat != "dialog":
            # non-dialog implementations are not affected by
            # 'dialog_version_check'.
            return True

        minimum_version = DialogBackendVersion.fromstring(version_string)
        res = (d.cached_backend_version >= minimum_version)

        if explain and not res:
            self.too_old_dialog_version(feature=feature, start=start,
                                        min=version_string)

        return res

    def too_old_dialog_version(self, feature="", **_3to2kwargs):
        if 'min' in _3to2kwargs: min = _3to2kwargs['min']; del _3to2kwargs['min']
        else: min = None
        if 'start' in _3to2kwargs: start = _3to2kwargs['start']; del _3to2kwargs['start']
        else: start = ""

        assert (feature and not start) or (not feature and start), \
            (feature, start)
        if not start:
            start = "Skipping {0},".format(feature)

        d.msgbox(
            "{start} because it requires dialog {min} or later; "
            "however, it appears that you are using version {used}.".format(
                start=start, min=min, used=d.cached_backend_version),
            width=60, height=9, title="Demo skipped")

    def progressbox_demo_with_filepath(self):
        widget = "progressbox"

        # First, ask the user for a file (possibly FIFO)
        d.msgbox(self.FIFO_HELP(widget), width=72, height=20)
        path = self.fselect_demo(widget, allow_FIFOs=True,
                                 title="Please choose a file to be shown as "
                                 "with 'tail -f'")
        if path is None:
            # User chose to abort
            return
        else:
            d.progressbox(file_path=path,
                          text="You can put some header text here",
                          title="Progressbox example with a file path")

    def progressboxoid(self, widget, func_name, text):
        # Since this is just a demo, I will not try to catch os.error exceptions
        # in this function, for the sake of readability.
        read_fd, write_fd = os.pipe()

        child_pid = os.fork()
        if child_pid == 0:
            try:
                # We are in the child process. We MUST NOT raise any exception.
                # No need for this one in the child process
                os.close(read_fd)

                # Python file objects are easier to use than file descriptors.
                # For a start, you don't have to check the number of bytes
                # actually written every time...
                # "buffering = 1" means wfile is going to be line-buffered
                with open(write_fd, mode="w", buffering=1) as wfile:
                    for line in text.split('\n'):
                        wfile.write(line + '\n')
                        time.sleep(0.02 if params["fast_mode"] else 1.2)

                os._exit(0)
            except:
                os._exit(127)

        # We are in the father process. No need for write_fd anymore.
        os.close(write_fd)
        # Call d.progressbox() if widget == "progressbox"
        #      d.programbox() if widget == "programbox"
        # etc.
        getattr(d, widget)(
            fd=read_fd,
            title="{0} example with a file descriptor".format(widget))

        # Now that the progressbox is over (second child process, running the
        # dialog-like program), we can wait() for the first child process.
        # Otherwise, we could have a deadlock in case the pipe gets full, since
        # dialog wouldn't be reading it.
        exit_info = os.waitpid(child_pid, 0)[1]
        if os.WIFEXITED(exit_info):
            exit_code = os.WEXITSTATUS(exit_info)
        elif os.WIFSIGNALED(exit_info):
            d.msgbox("%s(): first child process terminated by signal %d" %
                     (func_name, os.WTERMSIG(exit_info)))
        else:
            assert False, "How the hell did we manage to get here?"

        if exit_code != 0:
            d.msgbox("%s(): first child process ended with exit status %d"
                     % (func_name, exit_code))

    def progressbox_demo_with_file_descriptor(self):
        func_name = "progressbox_demo_with_file_descriptor"
        text = """\
A long time ago in a galaxy far,
far away...





A NEW HOPE

It was a period of intense
sucking. Graphical toolkits for
Python were all nice and clean,
but they were, well, graphical.
And as every one knows, REAL
PROGRAMMERS ALWAYS WORK ON VT-100
TERMINALS. In text mode.

Besides, those graphical toolkits
were usually too complex for
simple programs, so most FLOSS
geeks ended up writing
command-line tools except when
they really needed the full power
of mainstream graphical toolkits,
such as Qt, GTK+ and wxWidgets.

But... thanks to people like
Thomas E. Dickey, there are now
at our disposal several free
software command-line programs,
such as dialog, that allow easy
building of graphically-oriented
interfaces in text-mode
terminals. These are good for
tasks where line-oriented
interfaces are not well suited,
as well as for the increasingly
common type who runs away as soon
as he sees something remotely
resembling a command line.

But this is not for Python! I want
my poney!

Seeing this unacceptable
situation, Robb Shecter had the
idea, back in the olden days of
Y2K (when the world was supposed
to suddenly collapse, remember?),
to wrap a dialog interface into a
Python module called dialog.py.

pythondialog was born. Florent
Rougon, who was looking for
something like that in 2002,
found the idea rather cool and
improved the module during the
following years...""" + 15*'\n'

        return self.progressboxoid("progressbox", func_name, text)

    def programbox_demo(self):
        func_name = "programbox_demo"
        text = """\
The 'progressbox' widget
has a little brother
called 'programbox'
that displays text
read from a pipe
and only adds an OK button
when the pipe indicates EOF
(End Of File).

This can be used
to display the output
of some external program.

This will be done right away if you choose "Yes" in the next dialog.
This choice will cause 'find /usr/bin' to be run with subprocess.Popen()
and the output to be displayed, via a pipe, in a 'programbox' widget.\n"""
        self.progressboxoid("programbox", func_name, text)

        if d.Yesno("Do you want to run 'find /usr/bin' in a programbox widget?"):
            try:
                devnull = subprocess.DEVNULL
            except AttributeError: # Python < 3.3
                devnull_context = devnull = open(os.devnull, "wb")
            else:
                devnull_context = DummyContextManager()

            args = ["find", "/usr/bin"]
            with devnull_context:
                p = subprocess.Popen(args, stdout=subprocess.PIPE,
                                     stderr=devnull, close_fds=True)
                # One could use title=... instead of text=... to put the text
                # in the title bar.
                d.programbox(fd=p.stdout.fileno(),
                             text="Example showing the output of a command "
                             "with programbox")
                retcode = p.wait()

            # Context manager support for subprocess.Popen objects requires
            # Python 3.2 or later.
            p.stdout.close()
            return retcode
        else:
            return None

    def infobox_demo(self):
        d.infobox("One moment, please. Just wasting some time here to "
                  "show you the infobox...")

        time.sleep(0.5 if params["fast_mode"] else 4.0)

    def gauge_demo(self):
        d.gauge_start("Progress: 0%", title="Still testing your patience...")

        for i in xrange(1, 101):
            if i < 50:
                d.gauge_update(i, "Progress: {0}%".format(i), update_text=True)
            elif i == 50:
                d.gauge_update(i, "Over {0}%. Good.".format(i),
                               update_text=True)
            elif i == 80:
                d.gauge_update(i, "Yeah, this boring crap will be over Really "
                               "Soon Now.", update_text=True)
            else:
                d.gauge_update(i)

            time.sleep(0.01 if params["fast_mode"] else 0.1)

        d.gauge_stop()

    def mixedgauge_demo(self):
        for i in xrange(1, 101, 20):
            d.mixedgauge("This is the 'text' part of the mixedgauge\n"
                         "and this is a forced new line.",
                         title="'mixedgauge' demo",
                         percent=int(round(72+28*i/100)),
                         elements=[("Task 1", "Foobar"),
                                   ("Task 2", 0),
                                   ("Task 3", 1),
                                   ("Task 4", 2),
                                   ("Task 5", 3),
                                   ("", 8),
                                   ("Task 6", 5),
                                   ("Task 7", 6),
                                   ("Task 8", 7),
                                   ("", ""),
                                   # 0 is the dialog special code for
                                   # "Succeeded", so these must not be equal to
                                   # zero! That is why I made the range() above
                                   # start at 1.
                                   ("Task 9", -max(1, 100-i)),
                                   ("Task 10", -i)])
            time.sleep(0.5 if params["fast_mode"] else 2)

    def yesno_demo(self, with_help=True):
        if not with_help:
            # Simple version, without the "Help" button (the return value is
            # True or False):
            return d.Yesno("\nDo you like this demo?", yes_label="Yes, I do",
                           no_label="No, I do not", height=10, width=40,
                           title="An Important Question")

        # 'yesno' dialog box with custom Yes, No and Help buttons
        while True:
            reply = d.Yesnohelp("\nDo you like this demo?",
                                yes_label="Yes, I do", no_label="No, I do not",
                                help_label="Please help me!", height=10,
                                width=60, title="An Important Question")
            if reply == "yes":
                return True
            elif reply == "no":
                return False
            elif reply == "help":
                d.msgbox("""\
I can hear your cry for help, and would really like to help you. However, I \
am afraid there is not much I can do for you here; you will have to decide \
for yourself on this matter.

Keep in mind that you can always rely on me. \
You have all my support, be brave!""",
                         height=15, width=60,
                         title="From Your Faithful Servant")
            else:
                assert False, "Unexpected reply from MyDialog.Yesnohelp(): " \
                    + repr(reply)

    def msgbox_demo(self, answer):
        if answer:
            msg = "Excellent! Press OK to see its source code (or another " \
            "file if not in the correct directory)."
        else:
            msg = "Well, feel free to send your complaints to /dev/null!\n\n" \
                "Sincerely yours, etc."

        d.msgbox(msg, width=50)

    def textbox_demo(self):
        # Better use the absolute path for displaying in the dialog title
        filepath = os.path.abspath(__file__)
        code = d.textbox(filepath, width=76,
                         title="Contents of {0}".format(filepath),
                         extra_button=True, extra_label="Stop it now!")

        if code == "extra":
            d.msgbox("Your wish is my command, Master.", width=40,
                     title="Exiting")
            sys.exit(0)

    def inputbox_demo(self):
        code, answer = d.inputbox("What's your name?", init="Snow White")
        return answer

    def inputbox_demo_with_help(self):
        init_str = "Snow White"
        while True:
            code, answer = d.inputbox("What's your name?", init=init_str,
                                      title="'inputbox' demo", help_button=True)

            if code == "help":
                d.msgbox("Help from the 'inputbox' demo. The string entered "
                         "so far is {0!r}.".format(answer),
                         title="'inputbox' demo")
                init_str = answer
            else:
                break

        return answer

    def form_demo(self):
        elements = [
            ("Size (cm)", 1, 1, "175", 1, 20, 4, 3),
            ("Weight (kg)", 2, 1, "85", 2, 20, 4, 3),
            ("City", 3, 1, "Groboule-les-Bains", 3, 20, 15, 25),
            ("State", 4, 1, "Some Lost Place", 4, 20, 15, 25),
            ("Country", 5, 1, "Nowhereland", 5, 20, 15, 20),
            ("My", 6, 1, "I hereby declare that, upon leaving this "
             "world, all", 6, 20, 0, 0),
            ("Very", 7, 1, "my fortune shall be transferred to Florent "
             "Rougon's", 7, 20, 0, 0),
            ("Last", 8, 1, "bank account number 000 4237 4587 32454/78 at "
             "Banque", 8, 20, 0, 0),
            ("Will", 9, 1, "Cantonale Vaudoise, Lausanne, Switzerland.",
             9, 20, 0, 0) ]

        code, fields = d.form("Please fill in some personal information:",
                              elements, width=77)
        return fields

    def form_demo_with_help(self, item_help=True):
        # This function is slightly complex because it provides help support
        # with 'help_status=True', and optionally also with 'item_help=True'
        # together with 'help_tags=True'. For a very simple version (without
        # any help support), see form_demo() above.
        minver_for_helptags = "1.2-20130902"

        if item_help:
            if self.dialog_version_check(minver_for_helptags):
                complement = """'item_help=True' is also used in conjunction \
with 'help_tags=True' in order to display per-item help at the bottom of the \
widget."""
            else:
                item_help = False
                complement = """'item_help=True' is not used, because to make \
it consistent with the 'item_help=False' case, dialog {min} or later is \
required (for the --help-tags option); however, it appears that you are using \
version {used}.""".format(min=minver_for_helptags,
                          used=d.cached_backend_version)
        else:
            complement = """'item_help=True' is not used, because it has \
been disabled; therefore, there is no per-item help at the bottom of the \
widget."""

        text = """\
This is a demo for the 'form' widget, which is similar to 'mixedform' but \
a bit simpler in that it has no notion of field type (to hide contents such \
as passwords).

This demo uses 'help_button=True' to provide a Help button \
and 'help_status=True' to allow redisplaying the widget in the same state \
when leaving the help dialog. {complement}""".format(complement=complement)

        elements = [ ("Fruit",  1, 8, "mirabelle plum",  1, 20, 18, 30),
                     ("Color",  2, 8, "yellowish",       2, 20, 18, 30),
                     ("Flavor", 3, 8, "sweet when ripe", 3, 20, 18, 30),
                     ("Origin", 4, 8, "Lorraine",        4, 20, 18, 30) ]

        more_kwargs = {}

        if item_help:
            more_kwargs.update({ "item_help": True,
                                 "help_tags": True })
            elements = [ list(l) + [ "Help text for item {0}".format(i+1) ]
                         for i, l in enumerate(elements) ]

        while True:
            code, t = d.form(text, elements, height=20, width=65,
                             title="'form' demo with help facilities",
                             help_button=True, help_status=True, **more_kwargs)

            if code == "help":
                label, status, elements = t
                d.msgbox("You asked for help concerning the field labelled "
                         "{0!r}.".format(label), width=50)
            else:
                # 't' contains the list of items as filled by the user
                break

        answers = '\n'.join(t)
        d.msgbox("Your answers:\n\n{0}".format(indent(answers, "  ")),
                 width=0, height=0,
                 title="'form' demo with help facilities", no_collapse=True)
        return t

    def mixedform_demo(self):
        HIDDEN    = 0x1
        READ_ONLY = 0x2

        elements = [
            ("Size (cm)", 1, 1, "175", 1, 20, 4, 3, 0x0),
            ("Weight (kg)", 2, 1, "85", 2, 20, 4, 3, 0x0),
            ("City", 3, 1, "Groboule-les-Bains", 3, 20, 15, 25, 0x0),
            ("State", 4, 1, "Some Lost Place", 4, 20, 15, 25, 0x0),
            ("Country", 5, 1, "Nowhereland", 5, 20, 15, 20, 0x0),
            ("My", 6, 1, "I hereby declare that, upon leaving this "
             "world, all", 6, 20, 54, 0, READ_ONLY),
            ("Very", 7, 1, "my fortune shall be transferred to Florent "
             "Rougon's", 7, 20, 54, 0, READ_ONLY),
            ("Last", 8, 1, "bank account number 000 4237 4587 32454/78 at "
             "Banque", 8, 20, 54, 0, READ_ONLY),
            ("Will", 9, 1, "Cantonale Vaudoise, Lausanne, Switzerland.",
             9, 20, 54, 0, READ_ONLY),
            ("Read-only field...", 10, 1, "... that doesn't go into the "
             "output list", 10, 20, 0, 0, 0x0),
            ("\/3r`/ 53kri7 (0d3", 11, 1, "", 11, 20, 15, 20, HIDDEN) ]

        code, fields = d.mixedform(
            "Please fill in some personal information:", elements, width=77)

        return fields

    def passwordform_demo(self):
        elements = [
            ("Secret field 1", 1, 1, "", 1, 20, 12, 0),
            ("Secret field 2", 2, 1, "", 2, 20, 12, 0),
            ("Secret field 3", 3, 1, "Providing a non-empty initial content "
             "(like this) for an invisible field can be very confusing!",
             3, 20, 30, 160)]

        code, fields = d.passwordform(
            "Please enter all your secret passwords.\n\nOn purpose here, "
            "nothing is echoed when you type in the passwords. If you want "
            "asterisks, use the 'insecure' keyword argument as in the "
            "passwordbox demo.",
            elements, width=77, height=15, title="Passwordform demo")

        d.msgbox("Secret password 1: '%s'\n"
                 "Secret password 2: '%s'\n"
                 "Secret password 3: '%s'" % tuple(fields),
                 width=60, height=20, title="The Whole Truth Now Revealed")

        return fields

    def menu_demo(self, name, city, state, country, size, weight, secret_code,
                  last_will1, last_will2, last_will3, last_will4):
        text = """\
Hello, %s from %s, %s, %s, %s cm, %s kg.
Thank you for giving us your Very Secret Code '%s'.

As expressly stated in the previous form, your Last Will reads: "%s"

All that was very interesting, thank you. However, in order to know you \
better and provide you with the best possible customer service, we would \
still need to know your favorite day of the week. Please indicate your \
preference below.""" \
            % (name, city, state, country, size, weight, secret_code,
               ' '.join([last_will1, last_will2, last_will3, last_will4]))

        code, tag = d.menu(text, height=23, width=76,
            choices=[("Monday", "Being the first day of the week..."),
                     ("Tuesday", "Comes after Monday"),
                     ("Wednesday", "Before Thursday day"),
                     ("Thursday", "Itself after Wednesday"),
                     ("Friday", "The best day of all"),
                     ("Saturday", "Well, I've had enough, thanks"),
                     ("Sunday", "Let's rest a little bit")])

        return tag

    def menu_demo_with_help(self):
        text = """Sample 'menu' dialog box with help_button=True and \
item_help=True."""

        while True:
            code, tag = d.menu(text, height=16, width=60,
                choices=[("Tag 1", "Item 1", "Help text for item 1"),
                         ("Tag 2", "Item 2", "Help text for item 2"),
                         ("Tag 3", "Item 3", "Help text for item 3"),
                         ("Tag 4", "Item 4", "Help text for item 4"),
                         ("Tag 5", "Item 5", "Help text for item 5"),
                         ("Tag 6", "Item 6", "Help text for item 6"),
                         ("Tag 7", "Item 7", "Help text for item 7"),
                         ("Tag 8", "Item 8", "Help text for item 8")],
                               title="A menu with help facilities",
                               help_button=True, item_help=True, help_tags=True)

            if code == "help":
                d.msgbox("You asked for help concerning the item identified by "
                         "tag {0!r}.".format(tag), height=8, width=40)
            else:
                break

        d.msgbox("You have chosen the item identified by tag "
                 "{0!r}.".format(tag), height=8, width=40)

    def checklist_demo(self):
        # We could put non-empty items here (not only the tag for each entry)
        code, tags = d.checklist(text="What sandwich toppings do you like?",
                                 height=15, width=54, list_height=7,
                                 choices=[("Catsup", "",             False),
                                          ("Mustard", "",            False),
                                          ("Pesto", "",              False),
                                          ("Mayonnaise", "",          True),
                                          ("Horse radish","",        True),
                                          ("Sun-dried tomatoes", "", True)],
                                 title="Do you prefer ham or spam?",
                                 backtitle="And now, for something "
                                 "completely different...")
        return tags

    SAMPLE_DATA_FOR_BUILDLIST_AND_CHECKLIST = [
        ("Tag 1", "Item 1", True,  "Help text for item 1"),
        ("Tag 2", "Item 2", False, "Help text for item 2"),
        ("Tag 3", "Item 3", False, "Help text for item 3"),
        ("Tag 4", "Item 4", True,  "Help text for item 4"),
        ("Tag 5", "Item 5", True,  "Help text for item 5"),
        ("Tag 6", "Item 6", False, "Help text for item 6"),
        ("Tag 7", "Item 7", True,  "Help text for item 7"),
        ("Tag 8", "Item 8", False, "Help text for item 8") ]

    def checklist_demo_with_help(self):
        text = """Sample 'checklist' dialog box with help_button=True, \
item_help=True and help_status=True."""
        choices = self.SAMPLE_DATA_FOR_BUILDLIST_AND_CHECKLIST

        while True:
            code, t = d.checklist(text, height=0, width=0, list_height=0,
                                  choices=choices,
                                  title="A checklist with help facilities",
                                  help_button=True, item_help=True,
                                  help_tags=True, help_status=True)
            if code == "help":
                tag, selected_tags, choices = t
                d.msgbox("You asked for help concerning the item identified "
                         "by tag {0!r}.".format(tag), height=7, width=60)
            else:
                # 't' contains the list of tags corresponding to checked items
                break

        s = '\n'.join(t)
        d.msgbox("The tags corresponding to checked items are:\n\n"
                 "{0}".format(indent(s, "  ")), height=15, width=60,
                 title="'checklist' demo with help facilities",
                 no_collapse=True)

    def radiolist_demo(self):
        choices = [
            ("Hamburger",       "2 slices of bread, a steak...", False),
            ("Hotdog",          "doesn't bite any more",         False),
            ("Burrito",         "no se lo que es",               False),
            ("Doener",          "Huh?",                          False),
            ("Falafel",         "Erm...",                        False),
            ("Bagel",           "Of course!",                    False),
            ("Big Mac",         "Ah, that's easy!",              True),
            ("Whopper",         "Erm, sorry",                    False),
            ("Quarter Pounder", 'called "le Big Mac" in France', False),
            ("Peanut Butter and Jelly", "Well, that's your own business...",
                                                                 False),
            ("Grilled cheese",  "And nothing more?",             False) ]

        while True:
            code, t = d.radiolist(
                "What's your favorite kind of sandwich?", width=68,
                choices=choices, help_button=True, help_status=True)

            if code == "help":
                # Prepare to redisplay the radiolist in the same state as it
                # was before the user pressed the Help button.
                tag, selected, choices = t
                d.msgbox("You asked for help about something called {0!r}. "
                         "Sorry, but I am quite incompetent in this matter."
                         .format(tag))
            else:
                # 't' is the chosen tag
                break

        return t

    def rangebox_demo(self):
        nb = 10                 # initial value

        while True:
            code, nb = d.rangebox("""\
How many Microsoft(TM) engineers are needed to prepare such a sandwich?

You can use the Up and Down arrows, Page Up and Page Down, Home and End keys \
to change the value; you may also use the Tab key, Left and Right arrows \
and any of the 0-9 keys to change a digit of the value.""",
                                  min=1, max=20, init=nb,
                                  extra_button=True, extra_label="Joker")
            if code == "ok":
                break
            elif code == "extra":
                d.msgbox("Well, {0} may be enough. Or not, depending on the "
                         "phase of the moon...".format(nb))
            else:
                assert False, "Unexpected Dialog exit code: {0!r}".format(code)

        return nb

    def buildlist_demo(self):
        items0 = [("A Monty Python DVD",                             False),
                  ("A Monty Python script",                          False),
                  ('A DVD of "Barry Lyndon" by Stanley Kubrick',     False),
                  ('A DVD of "The Good, the Bad and the Ugly" by Sergio Leone',
                                                                     False),
                  ('A DVD of "The Trial" by Orson Welles',           False),
                  ('The Trial, by Franz Kafka',                      False),
                  ('Animal Farm, by George Orwell',                  False),
                  ('Notre-Dame de Paris, by Victor Hugo',            False),
                  ('Les Misérables, by Victor Hugo',                 False),
                  ('Le Lys dans la Vallée, by Honoré de Balzac',     False),
                  ('Les Rois Maudits, by Maurice Druon',             False),
                  ('A Georges Brassens CD',                          False),
                  ("A book of Georges Brassens' songs",              False),
                  ('A Nina Simone CD',                               False),
                  ('Javier Vazquez y su Salsa - La Verdad',          False),
                  ('The last Justin Bieber album',                   False),
                  ('A printed copy of the Linux kernel source code', False),
                  ('A CD player',                                    False),
                  ('A DVD player',                                   False),
                  ('An MP3 player',                                  False)]

        # Use the name as tag, item string and item-help string; the item-help
        # will be useful for long names because it is displayed in a place
        # that is large enough to avoid truncation. If not using
        # item_help=True, then the last element of eash tuple must be omitted.
        items = [ (tag, tag, status, tag) for (tag, status) in items0 ]

        text = """If you were stranded on a desert island, what would you \
take?

Press the space bar to toggle the status of an item between selected (on \
the left) and unselected (on the right). You can use the TAB key or \
^ and $ to change the focus between the different parts of the widget.

(this widget is called with item_help=True and visit_items=True)"""

        code, l = d.buildlist(text, items=items, visit_items=True,
                              item_help=True,
                              title="A simple 'buildlist' demo")
        return l

    def buildlist_demo_with_help(self):
        text = """Sample 'buildlist' dialog box with help_button=True, \
item_help=True, help_status=True, and visit_items=False.

Keys: SPACE   select or deselect the highlighted item, i.e.,
              move it between the left and right lists
      ^       move the focus to the left list
      $       move the focus to the right list
      TAB     move focus
      ENTER   press the focused button"""
        items = self.SAMPLE_DATA_FOR_BUILDLIST_AND_CHECKLIST

        while True:
            code, t = d.buildlist(text, height=0, width=0, list_height=0,
                                  items=items,
                                  title="A 'buildlist' with help facilities",
                                  help_button=True, item_help=True,
                                  help_tags=True, help_status=True,
                                  no_collapse=True)
            if code == "help":
                tag, selected_tags, items = t
                d.msgbox("You asked for help concerning the item identified "
                         "by tag {0!r}.".format(tag), height=7, width=60)
            else:
                # 't' contains the list of tags corresponding to selected items
                break

        s = '\n'.join(t)
        d.msgbox("The tags corresponding to selected items are:\n\n"
                 "{0}".format(indent(s, "  ")), height=15, width=60,
                 title="'buildlist' demo with help facilities",
                 no_collapse=True)

    def calendar_demo(self):
        code, date = d.calendar("When do you think Georg Cantor was born?")
        return date

    def calendar_demo_with_help(self):
        # Start with the current date
        day, month, year = 0, 0, 0

        while True:
            code, date = d.calendar("When do you think Georg Cantor was born?",
                                    day=day, month=month, year=year,
                                    title="'calendar' demo",
                                    help_button=True)
            if code == "help":
                day, month, year = date
                d.msgbox("Help dialog for date {0:04d}-{1:02d}-{2:02d}.".format(
                        year, month, day), title="'calendar' demo")
            else:
                break

        return date

    def comment_on_Cantor_date_of_birth(self, day, month, year):
        complement = """\
For your information, Georg Ferdinand Ludwig Philip Cantor, a great \
mathematician, was born on March 3, 1845 in Saint Petersburg, and died on \
January 6, 1918. Among other things, Georg Cantor laid the foundation for \
the set theory (which is at the basis of most modern mathematics) \
and was the first person to give a rigorous definition of real numbers."""

        if (year, month, day) == (1845, 3, 3):
            return "Spot-on! I'm impressed."
        elif year == 1845:
            return "You guessed the year right. {0}".format(complement)
        elif abs(year-1845) < 30:
            return "Not too far. {0}".format(complement)
        else:
            return "Well, not quite. {0}".format(complement)

    def timebox_demo(self):
        # Get the current time (to display initially in the timebox)
        tm = time.localtime()
        init_hour, init_min, init_sec = tm.tm_hour, tm.tm_min, tm.tm_sec
        # tm.tm_sec can be 60 or even 61 according to the doc of the time module!
        init_sec = min(59, init_sec)

        code, (hour, minute, second) = d.timebox(
            "And at what time, if I may ask?",
            hour=init_hour, minute=init_min, second=init_sec)

        return (hour, minute, second)

    def passwordbox_demo(self):
        # 'insecure' keyword argument only asks dialog to echo asterisks when
        # the user types characters. Not *that* bad.
        code, password = d.passwordbox("What is your root password, "
                                       "so that I can crack your system "
                                       "right now?", insecure=True)
        return password

    def scrollbox_demo(self, name, favorite_day, toppings, sandwich,
                       nb_engineers, desert_island_stuff, date, time_,
                       password):
        tw71 = textwrap.TextWrapper(width=71, break_long_words=False,
                                    break_on_hyphens=True)

        if nb_engineers is not None:
            sandwich_comment = " (the preparation of which requires, " \
                "according to you, {nb_engineers} MS {engineers})".format(
                nb_engineers=nb_engineers,
                engineers="engineers" if nb_engineers != 1 else "engineer")
        else:
            sandwich_comment = ""

        sandwich_report = "Favorite sandwich: {sandwich}{comment}".format(
            sandwich=sandwich, comment=sandwich_comment)

        if len(desert_island_stuff) == 0:
            desert_island_string = " nothing!"
        else:
            desert_island_string = "\n\n  " + "\n  ".join(desert_island_stuff)

        day, month, year = date
        hour, minute, second = time_
        msg = """\
Here are some vital statistics about you:

Name: {name}
Favorite day of the week: {favday}
Favorite sandwich toppings:{toppings}
{sandwich_report}

On a desert island, you would take:{desert_island_string}

Your answer about Georg Cantor's date of birth: \
{year:04d}-{month:02d}-{day:02d}
(at precisely {hour:02d}:{min:02d}:{sec:02d}!)

{comment}

Your root password is: ************************** (looks good!)""".format(
            name=name, favday=favorite_day,
            toppings="\n    ".join([''] + toppings),
            sandwich_report=tw71.fill(sandwich_report),
            desert_island_string=desert_island_string,
            year=year, month=month, day=day,
            hour=hour, min=minute, sec=second,
            comment=tw71.fill(
              self.comment_on_Cantor_date_of_birth(day, month, year)))
        d.scrollbox(msg, height=20, width=75, title="Great Report of the Year")

    TREEVIEW_BASE_TEXT = """\
This is an example of the 'treeview' widget{options}. Nodes are labelled in a \
way that reflects their position in the tree, but this is not a requirement: \
you are free to name them the way you like.

Node 0 is the root node. It has 3 children tagged 0.1, 0.2 and 0.3. \
You should now select a node with the space bar."""

    def treeview_demo(self):
        code, tag = d.treeview(self.TREEVIEW_BASE_TEXT.format(options=""),
                               nodes=[ ("0", "node 0", False, 0),
                                       ("0.1", "node 0.1", False, 1),
                                       ("0.2", "node 0.2", False, 1),
                                       ("0.2.1", "node 0.2.1", False, 2),
                                       ("0.2.1.1", "node 0.2.1.1", True, 3),
                                       ("0.2.2", "node 0.2.2", False, 2),
                                       ("0.3", "node 0.3", False, 1),
                                       ("0.3.1", "node 0.3.1", False, 2),
                                       ("0.3.2", "node 0.3.2", False, 2) ],
                               title="'treeview' demo")

        d.msgbox("You selected the node tagged {0!r}.".format(tag),
                 title="treeview demo")
        return tag

    def treeview_demo_with_help(self):
        text = self.TREEVIEW_BASE_TEXT.format(
            options=" with help_button=True, item_help=True and "
            "help_status=True")

        nodes = [ ("0",       "node 0",       False, 0, "Help text 1"),
                  ("0.1",     "node 0.1",     False, 1, "Help text 2"),
                  ("0.2",     "node 0.2",     False, 1, "Help text 3"),
                  ("0.2.1",   "node 0.2.1",   False, 2, "Help text 4"),
                  ("0.2.1.1", "node 0.2.1.1", True,  3, "Help text 5"),
                  ("0.2.2",   "node 0.2.2",   False, 2, "Help text 6"),
                  ("0.3",     "node 0.3",     False, 1, "Help text 7"),
                  ("0.3.1",   "node 0.3.1",   False, 2, "Help text 8"),
                  ("0.3.2",   "node 0.3.2",   False, 2, "Help text 9") ]

        while True:
            code, t = d.treeview(text, nodes=nodes,
                                 title="'treeview' demo with help facilities",
                                 help_button=True, item_help=True,
                                 help_tags=True, help_status=True)

            if code == "help":
                # Prepare to redisplay the treeview in the same state as it
                # was before the user pressed the Help button.
                tag, selected_tag, nodes = t
                d.msgbox("You asked for help about the node with tag {0!r}."
                         .format(tag))
            else:
                # 't' is the chosen tag
                break

        d.msgbox("You selected the node tagged {0!r}.".format(t),
                 title="'treeview' demo")
        return t

    def editbox_demo(self, filepath):
        if os.path.isfile(filepath):
            code, text = d.editbox(filepath, 20, 60,
                                   title="A Cheap Text Editor")

        d.scrollbox(text, title="Resulting text")

    def inputmenu_demo(self):
        choices = [ ("1st_tag", "Item 1 text"),
                    ("2nd_tag", "Item 2 text"),
                    ("3rd_tag", "Item 3 text") ]

        for i in xrange(4, 21):
            choices.append(("%dth_tag" % i, "Item %d text" % i))

        while True:
            code, tag, new_item_text = d.inputmenu(
                "Demonstration of 'inputmenu'. Any single item can be either "
                "accepted as is, or renamed.",
                height=0, width=60, menu_height=10, choices=choices,
                help_button=True, title="'inputmenu' demo")

            if code == "help":
                d.msgbox("You asked for help about the item with tag {0!r}."
                         .format(tag))
                continue
            elif code == "accepted":
                text = "The item corresponding to tag {0!r} was " \
                    "accepted.".format(tag)
            elif code == "renamed":
                text = "The item corresponding to tag {0!r} was renamed to " \
                    "{1!r}.".format(tag, new_item_text)
            else:
                text = "Unexpected exit code from 'inputmenu': {0!r}.\n\n" \
                    "It may be a bug. Please report.".format(code)

            break

        d.msgbox(text, width=60, title="Outcome of the 'inputmenu' demo")

    # Help strings used in several places
    FSELECT_HELP = """\
Hint: the complete file path must be entered in the bottom field. One \
convenient way to achieve this is to use the SPACE bar when the desired file \
is highlighted in the top-right list.

As usual, you can use the TAB and arrow keys to move between controls. If in \
the bottom field, the SPACE key provides auto-completion."""

    # The following help text was initially meant to be used for several
    # widgets (at least progressbox and tailbox). Currently (dialog version
    # 1.2-20130902), "dialog --tailbox" doesn't seem to work with FIFOs, so the
    # "flexibility" of the help text is unused (another text is used when
    # demonstrating --tailbox). However, this might change in the future...
    def FIFO_HELP(self, widget):
        return """\
For demos based on the {widget} widget, you may use a FIFO, also called \
"named pipe". This is a special kind of file, to which you will be able to \
easily append data. With the {widget} widget, you can see the data stream \
flow in real time.

To create a FIFO, you can use the commmand mkfifo(1), like this:

  % mkfifo /tmp/my_shiny_new_fifo

Then, you can cat(1) data to the FIFO like this:

  % cat >>/tmp/my_shiny_new_fifo
  First line of text
  Second line of text
  ...

You can end the input to cat(1) by typing Ctrl-D at the beginning of a \
line.""".format(widget=widget)

    def fselect_demo(self, widget, init_path=None, allow_FIFOs=False, **kwargs):
        init_path = init_path or params["home_dir"]
        # Make sure the directory we chose ends with os.sep so that dialog
        # shows its contents right away
        if not init_path.endswith(os.sep):
            init_path += os.sep

        while True:
            # We want to let the user quit this particular dialog with Cancel
            # without having to bother choosing a file, therefore we use the
            # original fselect() from dialog.Dialog and interpret the return
            # code manually. (By default, the MyDialog class defined in this
            # file intercepts the CANCEL and ESC exit codes and causes them to
            # spawn the "confirm quit" dialog.)
            code, path = self.Dialog_instance.fselect(
                init_path, height=10, width=60, help_button=True, **kwargs)

            # Display the "confirm quit" dialog if the user pressed ESC.
            if not d.check_exit_request(code, ignore_Cancel=True):
                continue

            # Provide an easy way out...
            if code == d.CANCEL:
                path = None
                break
            elif code == "help":
                d.msgbox("Help about {0!r} from the 'fselect' dialog.".format(
                        path), title="'fselect' demo")
                init_path = path
            elif code == d.OK:
                # Of course, one can use os.path.isfile(path) here, but we want
                # to allow regular files *and* possibly FIFOs. Since there is
                # no os.path.is*** convenience function for FIFOs, let's go
                # with os.stat.
                try:
                    mode = os.stat(path)[stat.ST_MODE]
                except os.error, e:
                    d.msgbox("Error: {0}".format(e))
                    continue

                # Accept FIFOs only if allow_FIFOs is True
                if stat.S_ISREG(mode) or (allow_FIFOs and stat.S_ISFIFO(mode)):
                    break
                else:
                    if allow_FIFOs:
                        help_text = """\
You are expected to select a *file* here (possibly a FIFO), or press the \
Cancel button.\n\n%s

For your convenience, I will reproduce the FIFO help text here:\n\n%s""" \
                            % (self.FSELECT_HELP, self.FIFO_HELP(widget))
                    else:
                        help_text = """\
You are expected to select a regular *file* here, or press the \
Cancel button.\n\n%s""" % (self.FSELECT_HELP,)

                    d.msgbox(help_text, width=72, height=20)
            else:
                d.msgbox("Unexpected exit code from Dialog.fselect(): {0}.\n\n"
                         "It may be a bug. Please report.".format(code))
        return path

    def dselect_demo(self, init_dir=None):
        init_dir = init_dir or params["home_dir"]
        # Make sure the directory we chose ends with os.sep so that dialog
        # shows its contents right away
        if not init_dir.endswith(os.sep):
            init_dir += os.sep

        while True:
            code, path = d.dselect(init_dir, 10, 50,
                                   title="Please choose a directory",
                                   help_button=True)
            if code == "help":
                d.msgbox("Help about {0!r} from the 'dselect' dialog.".format(
                        path), title="'dselect' demo")
                init_dir = path
            # When Python 3.2 is old enough, we'll be able to check if
            # path.endswith(os.sep) and remove the trailing os.sep if this
            # does not change the path according to os.path.samefile().
            elif not os.path.isdir(path):
                d.msgbox("Hmm. It seems that {0!r} is not a directory".format(
                        path), title="'dselect' demo")
            else:
                break

        d.msgbox("Directory '%s' thanks you for choosing him." % path)
        return path

    def tailbox_demo(self, height=22, width=78):
        widget = "tailbox"

        # First, ask the user for a file.
        # Strangely (dialog version 1.2-20130902 bug?), "dialog --tailbox"
        # doesn't work with FIFOs: "Error moving file pointer in last_lines()"
        # and DIALOG_ERROR exit status.
        path = self.fselect_demo(widget, allow_FIFOs=False,
                                 title="Please choose a file to be shown as "
                                 "with 'tail -f'")
        # Now, the tailbox
        if path is None:
            # User chose to abort
            return
        else:
            d.tailbox(path, height, width, title="Tailbox example")

    def pause_demo(self, seconds):
        d.pause("""\
Ugh, sorry. pythondialog is still in development, and its advanced circuitry \
detected internal error number 0x666. That's a pretty nasty one, you know.

I am embarrassed. I don't know how to tell you, but we are going to have to \
reboot. In %d seconds.

Fasten your seatbelt...""" % seconds, height=18, seconds=seconds)


def process_command_line():
    global params

    try:
        opts, args = getopt.getopt(sys.argv[1:], "ft",
                                   ["test-suite",
                                    "fast",
                                    "debug",
                                    "debug-file=",
                                    "help",
                                    "version"])
    except getopt.GetoptError:
        print(usage, file=u_stderr)
        return ("exit", 1)

    # Let's start with the options that don't require any non-option argument
    # to be present
    for option, value in opts:
        if option == "--help":
            print(usage, file=u_stdout)
            return ("exit", 0)
        elif option == "--version":
            print("%s %s\n%s" % (progname, progversion, version_blurb),
                  file=u_stdout)
            return ("exit", 0)

    # Now, require a correct invocation.
    if len(args) != 0:
        print(usage, file=u_stderr)
        return ("exit", 1)

    # Default values for parameters
    params = { "fast_mode": False,
               "testsuite_mode": False,
               "debug": False,
               "debug_filename": default_debug_filename }

    # Get the home directory, if any, and store it in params (often useful).
    root_dir = os.sep           # This is OK for Unix-like systems
    params["home_dir"] = os.getenv("HOME", root_dir)

    # General option processing
    for option, value in opts:
        if option in ("-t", "--test-suite"):
            params["testsuite_mode"] = True
            # --test-suite implies --fast
            params["fast_mode"] = True
        elif option in ("-f", "--fast"):
            params["fast_mode"] = True
        elif option == "--debug":
            params["debug"] = True
        elif option == "--debug-file":
            params["debug_filename"] = value
        else:
            # The options (such as --help) that cause immediate exit
            # were already checked, and caused the function to return.
            # Therefore, if we are here, it can't be due to any of these
            # options.
            assert False, "Unexpected option received from the " \
                "getopt module: '%s'" % option

    return ("continue", None)


def main():
    """This demo shows the main features of pythondialog."""
    locale.setlocale(locale.LC_ALL, '')

    what_to_do, code = process_command_line()
    if what_to_do == "exit":
        sys.exit(code)

    try:
        app = MyApp()
        app.run()
    except dialog.error, exc_instance:
        # The error that causes a PythonDialogErrorBeforeExecInChildProcess to
        # be raised happens in the child process used to run the dialog-like
        # program, and the corresponding traceback is printed right away from
        # that child process when the error is encountered. Therefore, don't
        # print a second, not very useful traceback for this kind of exception.
        if not isinstance(exc_instance,
                          dialog.PythonDialogErrorBeforeExecInChildProcess):
            # traceback.format_exc() is a byte string in Python 2
            print(unicode(traceback.format_exc()), file=u_stderr)

        print("Error (see above for a traceback):\n\n{0}".format(
                exc_instance), file=u_stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__": main()
