# -*- coding: utf-8 -*-
"""
EvMore - pager mechanism

This is a pager for displaying long texts and allows stepping up and
down in the text (the name comes from the traditional 'more' unix
command).

To use, simply pass the text through the EvMore object:

    from evennia.utils.evmore import EvMore

    text = some_long_text_output()
    EvMore(caller, text, always_page=False, session=None, justify_kwargs=None, **kwargs)

One can also use the convenience function msg from this module:

    from evennia.utils import evmore

    text = some_long_text_output()
    evmore.msg(caller, text, always_page=False, session=None, justify_kwargs=None, **kwargs)

Where always_page decides if the pager is used also if the text is not
long enough to need to scroll, session is used to determine which session to relay to
and justify_kwargs are kwargs to pass to utils.utils.justify in order to change the formatting
of the text. The remaining **kwargs will be passed on to the
caller.msg() construct every time the page is updated.

"""
from builtins import object, range

from django.conf import settings
from evennia import Command, CmdSet
from evennia.commands import cmdhandler
from evennia.utils.utils import justify

_CMD_NOMATCH = cmdhandler.CMD_NOMATCH
_CMD_NOINPUT = cmdhandler.CMD_NOINPUT

# we need to use NAWS for this
_SCREEN_WIDTH = settings.CLIENT_DEFAULT_WIDTH
_SCREEN_HEIGHT = settings.CLIENT_DEFAULT_HEIGHT

# text

_DISPLAY = \
"""{text}
(|wmore|n [{pageno}/{pagemax}] retur|wn|n|||wb|nack|||wt|nop|||we|nnd|||wq|nuit)"""


class CmdMore(Command):
    """
    Manipulate the text paging
    """
    key = _CMD_NOINPUT
    aliases = ["quit", "q", "abort", "a", "next", "n",
               "back", "b", "top", "t", "end", "e"]
    auto_help = False

    def func(self):
        """
        Implement the command
        """
        more = self.caller.ndb._more
        if not more and hasattr(self.caller, "player"):
            more = self.caller.player.ndb._more
        if not more:
            self.caller.msg("Error in loading the pager. Contact an admin.")
            return

        cmd = self.cmdstring

        if cmd in ("abort", "a", "q"):
            more.page_quit()
        elif cmd in ("back", "b"):
            more.page_back()
        elif cmd in ("top", "t"):
            more.page_top()
        elif cmd in ("end", "e"):
            more.page_end()
        else:
            # return or n, next
            more.page_next()


class CmdSetMore(CmdSet):
    """
    Stores the more command
    """
    key = "more_commands"
    priority = 110

    def at_cmdset_creation(self):
        self.add(CmdMore)


class EvMore(object):
    """
    The main pager object
    """
    def __init__(self, caller, text, always_page=False, session=None, justify_kwargs=None, **kwargs):
        """
        Initialization of the text handler.

        Args:
            caller (Object or Player): Entity reading the text.
            text (str): The text to put under paging.
            always_page (bool, optional): If `False`, the
                pager will only kick in if `text` is too big
                to fit the screen.
            kwargs (any, optional): These will be passed on
                to the `caller.msg` method.

        """
        self._caller = caller
        self._kwargs = kwargs
        self._pages = []
        self._npages = []
        self._npos = []
        if not session:
            # if not supplied, use the first session to
            # determine screen size
            sessions = caller.sessions.get()
            if not sessions:
                return
            session = sessions[0]
        self._session = session

        # set up individual pages for different sessions
        height = session.protocol_flags.get("SCREENHEIGHT", {0:_SCREEN_HEIGHT})[0] - 2
        width = session.protocol_flags.get("SCREENWIDTH", {0:_SCREEN_WIDTH})[0]

        # we must break very long lines into multiple ones
        justify_kwargs = justify_kwargs or {}
        width = justify_kwargs.get("width", width)
        justify_kwargs["width"] = width
        justify_kwargs["align"] = justify_kwargs.get("align", 'l')
        justify_kwargs["indent"] = justify_kwargs.get("indent", 0)

        lines = justify(text, **justify_kwargs).split("\n")

        # always limit number of chars to 10 000 per page
        height = min(10000 // width, height)

        self._pages = ["\n".join(lines[i:i+height]) for i in range(0, len(lines), height)]
        self._npages = len(self._pages)
        self._npos = 0

        if self._npages <= 1 and not always_page:
            # no need for paging; just pass-through.
            caller.msg(text=text, **kwargs)
        else:
            # go into paging mode
            # first pass on the msg kwargs
            caller.ndb._more = self
            caller.cmdset.add(CmdSetMore)

            # goto top of the text
            self.page_top()

    def _display(self):
        """
        Pretty-print the page.
        """
        pos = self._pos
        text = self._pages[pos]
        page = _DISPLAY.format(text=text,
                               pageno=pos + 1,
                               pagemax=self._npages)
        self._caller.msg(text=page, session=self._session, **self._kwargs)

    def page_top(self):
        """
        Display the top page
        """
        self._pos = 0
        self._display()

    def page_end(self):
        """
        Display the bottom page.
        """
        self._pos = self._npages - 1
        self._display()

    def page_next(self):
        """
        Scroll the text to the next page. Quit if already at the end
        of the page.
        """
        if self._pos >= self._npages - 1:
            # exit if we are already at the end
            self.page_quit()
        else:
            self._pos += 1
            self._display()

    def page_back(self):
        """
        Scroll the text back up, at the most to the top.
        """
        self._pos = max(0, self._pos - 1)
        self._display()

    def page_quit(self):
        """
        Quit the pager
        """
        del self._caller.ndb._more
        self._caller.cmdset.remove(CmdSetMore)
        self._caller.msg("Exited |wmore|n pager.")


def msg(caller, text="", always_page=False, session=None, justify_kwargs=None, **kwargs):
    """
    More-supported version of msg, mimicking the
    normal msg method.
    """
    EvMore(caller, text, always_page=always_page, session=session,
                justify_kwargs=justify_kwargs, **kwargs)

