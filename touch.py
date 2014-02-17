"""
Thoughts:

- Remove individual regions and handlers, rather than whole views.
- Configurable on a view and/or handler level whether it is removed
  when the view is closed.
  Should we auto remove all when the view is closed?
- Functionality to add more than one region/handler at a time to a view.

"""

import time

import sublime_plugin
import sublime


TOUCH_EVENT_TIME = None
TOUCH_EVENT_HANDLERS = {}
TOUCH_EVENT_HANDLERS_ASYNC = {}


def add_event_handler(view, region, handler=None, HANDLERS=TOUCH_EVENT_HANDLERS):
    HANDLERS.setdefault(view.id(), []).append([region, handler])


def add_event_handler_async(view, region, handler):
    add_event_handler(view, region, handler, TOUCH_EVENT_HANDLERS_ASYNC)


def remove_event_handlers(view, HANDLERS=TOUCH_EVENT_HANDLERS):
    if view.id() in HANDLERS:
        del HANDLERS[view.id()]


def remove_event_handlers_async(view):
    remove_event_handlers(view, TOUCH_EVENT_HANDLERS_ASYNC)


def event_handler(view, HANDLERS=TOUCH_EVENT_HANDLERS):
    global TOUCH_EVENT_TIME
    if not view.id() in HANDLERS:
        return None
    regions = view.sel()
    event_time = time.time()
    if len(regions) == 1 and regions[0].empty() and (
        TOUCH_EVENT_TIME is None or
        TOUCH_EVENT_TIME < event_time - 0.2
    ):
        point = regions[0].begin()
        TOUCH_EVENT_TIME = event_time
        for region, handler in HANDLERS[view.id()]:
            if region.contains(point):
                handler(view, region, point)


class LiveEventListener(sublime_plugin.EventListener):
    def on_selection_modified(self, view):
        event_handler(view)

    def on_selection_modified_async(self, view):
        event_handler(view, TOUCH_EVENT_HANDLERS_ASYNC)

    def on_close(self, view):
        remove_event_handlers(view)
        remove_event_handlers_async(view)


###################
# UTILITIES
###################


class TouchEditViewContentCommand(sublime_plugin.TextCommand):
    def run(self, edit, data=None, start=0, end=None):
        was_read_only = self.view.is_read_only()
        if was_read_only:
            self.view.set_read_only(False)
        if end is not None and not start == end:
            if data is not None:
                self.view.replace(edit, sublime.Region(start, end), data)
            else:
                self.view.erase(edit, sublime.Region(start, end))
        elif data is not None:
            self.view.insert(edit, start, data)
        if was_read_only:
            self.view.set_read_only(True)
